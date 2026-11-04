+++
date = '2027-04-09T10:00:00+03:30'
draft = false
title = 'Authorization: RBAC and IDOR'
description = 'Authorization in Go on localhost: RBAC permissions, IDOR fixed with ownership checks and 404s, role escalation by mass assignment, and a route test.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "authorization", "rbac", "idor", "go"]
cover = { image = "/images/covers/sec-authorization-rbac-idor.png", alt = "Authorization: RBAC and IDOR", hiddenInSingle = true }
+++

Alice has an account on a document app. She opens one of her own documents and the address bar shows `/documents/1`. Out of curiosity she types `/documents/2`. If the app shows her somebody else's document, it has a very common bug: it checked that she is logged in, and never checked that the document is hers.

That is the difference between knowing who the caller is and deciding what the caller may do. The token that [OAuth2 and OIDC](/posts/sec-oauth2-oidc/) ended with answers the first question: who she is and what scopes she holds. The second question is {{< term "authorization" "authorization" >}}, and the server has to answer it again for every function and every object. The bug above is called {{< term "idor" "IDOR" >}} (insecure direct object reference): an object is fetched by its ID, and nobody checks that this caller may see it. I showed it briefly in [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/). Here I go deeper: roles, a second bug where a user promotes herself, and a test that guards every route. The API style is the [net/http one from earlier](/posts/go-http-api-stdlib/).

> Defensive only. One small Go program on `127.0.0.1` with in-memory data and my own code (Go 1.27.3 on macOS arm64; the demo's `go.mod` says 1.26). Authentication is simplified to fixed tokens (`tok-alice`, `tok-bob`, `tok-carol`) so that the focus stays on authorization. A `-mode vuln|fixed` flag builds each version. The users are alice (role `viewer`, tenant `acme`), bob (`editor`, tenant `globex`) and carol (`admin`, tenant `acme`). There are two documents: 1 is alice's, 2 is bob's. I sent the requests with `curl` against each build.

## 401, 403 or 404

Three status codes carry most of the story, so here is how I use them:

- **401**: I do not know who you are. No token, or a bad one.
- **403**: I know who you are, and you may not do this. Note that it also tells you the thing exists.
- **404**: what I answer for other people's objects, so a stranger cannot tell "not yours" from "not there".

## The vulnerable version

First the vulnerable build. Alice is only a viewer. She sends six requests, in this order (the `PATCH` body was `{"name":"alice","role":"admin"}`):

```
200 GET /documents/2 => {"id":2,"owner":"bob","title":"bob secret"}
404 GET /documents/99 => not found
200 GET /documents/1 => {"id":1,"owner":"alice","title":"alice plan"}
200 GET /admin/users => [{"name":"alice","tenant":"acme","role":"viewer"},{"name":"bob","tenant":"globex","role":"editor"},{"name":"carol","tenant":"acme","role":"admin"}]
200 PATCH /users/me => {"name":"alice","tenant":"acme","role":"admin"}
204 DELETE /documents/2 => 
```

The order of users in the list can differ between runs, because the demo keeps users in a map. The lines for documents 99 and 1 are the normal behaviour: a missing document is a 404, and her own document is readable. The other four are the problems:

1. **Object level.** She reads Bob's document just by asking for its ID. This is the IDOR.
2. **Function level.** She deletes a document, although a viewer should not be able to delete at all.
3. **Function level again.** She lists all users, which is an admin function.
4. {{< term "mass-assignment" "Mass assignment" >}}. The handler decodes the JSON she sends straight into the `User` struct, so she picked her own `role`. Her response says `"role":"admin"`.

According to the OWASP API Security Top 10 (2023 edition), the first is "API1: Broken Object Level Authorization", the second and third are "API5: Broken Function Level Authorization", and mass assignment is part of "API3: Broken Object Property Level Authorization".

Notice that none of these needed a clever attack. Each is just a request the server forgot to refuse.

## The fixes

**Object level.** Ownership becomes part of the lookup, and the answer for someone else's object is 404:

```go
if d == nil || d.Owner != u.Name {
    http.Error(w, "not found", 404)
    return
}
```

With a database, the same idea is `WHERE id = $1 AND owner_id = $2`: one query, so there is no separate "fetch, then check" step that somebody can forget. The demo uses a map; I did not run this against Postgres.

**Function level.** Roles map to permissions, and each route declares the permission it needs:

```go
var perms = map[string][]string{
    "viewer": {"doc:read"},
    "editor": {"doc:read", "doc:write"},
    "admin":  {"doc:read", "doc:write", "doc:delete", "users:read"},
}
a.protect("DELETE /documents/{id}", "doc:delete", a.deleteDoc)
```

The code checks the permission and never the role name. That is the point of {{< term "rbac" "RBAC" >}} (role-based access control): the roles are a table you can edit, and the handlers do not change when you add one. The wrapper `protect` first checks the token (401), then the permission (403).

**Mass assignment.** Decode into a type that lists exactly the fields a client may change:

```go
var in struct {
    Name string `json:"name"`
}
json.NewDecoder(r.Body).Decode(&in)
```

Now the same Alice, against the fixed build:

```
404 GET /documents/2 => not found
404 GET /documents/99 => not found
200 GET /documents/1 => {"id":1,"owner":"alice","title":"alice plan"}
403 GET /admin/users => forbidden
200 PATCH /users/me => {"name":"alice","tenant":"acme","role":"viewer"}
403 DELETE /documents/2 => forbidden
```

Read it from the top. Bob's document (2) and a document that does not exist (99) now look identical: Alice cannot even confirm that 2 exists. Her own document still works. The admin list and the delete are refused with 403, because a viewer has neither permission. And the `PATCH` that tried to set `role` returns `"role":"viewer"`: the extra field was simply ignored. Without any token the server answers `401` (and `/healthz` stays public, answering `ok`).

The server also logged each denial:

```
level=WARN msg="authz denied" user=alice doc=2 owner=bob
level=WARN msg="authz denied" user=alice role=viewer need=users:read route="GET /admin/users"
level=WARN msg="authz denied" user=alice role=viewer need=doc:delete route="DELETE /documents/{id}"
```

Log every denial with who, what and which rule ([structured logging](/posts/go-config-logging-errors/) makes this searchable). A burst of 404s and 403s from one user is what somebody trying IDs one after another looks like. Do not log tokens.

## What "fixed" still does not cover

The fixes above close the four holes, but I should be honest about a fifth one in this same fixed build. Carol is an admin of tenant `acme`, and Bob's document belongs to tenant `globex`. I made two extra requests with her token (these are not in the original demo script; I ran them against the same fixed build in a scratch copy):

```
404 GET /documents/2 => not found
204 DELETE /documents/2 => 
```

Reading Bob's document is refused, because the lookup includes the owner. But the delete went through. `deleteDoc` only needs the `doc:delete` permission and never checks whose document it is. The function-level check passed, and nobody added the object-level check there. This is the usual shape of the bug: the two kinds of check are separate, and each route needs both. The exercise below is to close this one.

## Deny by default, and a test that enforces it

A design rule helps with the "forgot a check" problem: {{< term "deny-by-default" "deny by default" >}}. Every route needs a valid token unless it is explicitly listed as public. A test then makes sure the rule survives future edits. Routes are registered through two helpers that record each pattern, and the test calls every route without a token:

```go
var publicRoutes = map[string]bool{"GET /healthz": true}
// for every registered route not in publicRoutes: expect 401
```

To see it catch something, I temporarily added an unprotected `GET /debug/vars` through the `public(...)` helper in a scratch copy. This is what `go test` printed:

```
--- FAIL: TestEveryRouteRequiresAuth (0.00s)
    --- FAIL: TestEveryRouteRequiresAuth/GET_/debug/vars (0.00s)
        routes_test.go:26: GET /debug/vars answered 200 without a token, want 401
FAIL
FAIL	authzdemo	0.321s
FAIL
```

The failing subtest names the route and the status it answered. After I removed the route the suite passed again (`TestViewerCannotDelete` also checks that a viewer gets 403). The limit of this test: it only knows about routes registered through my helpers. A handler wired onto the mux by hand is invisible to it.

## Beyond roles

RBAC gets awkward when a rule depends on attributes (owner, tenant, time of day) or on relationships ("a member of the team that owns this folder"). Attribute-based (ABAC) and relationship-based (ReBAC) models exist for those cases. I only mention them here; I did not run either.

## A checklist for every route

- Check authorization on the server, for every function and every object. Hiding a button in the UI is not a check, because the request can be sent without the button.
- Take the identity from the verified token, never from a user ID in the body or the URL. Otherwise the caller can claim to be somebody else.
- Decode requests into types that list the allowed fields, never straight into your database or domain struct. Otherwise the client decides fields such as `role`.
- Be consistent in what you answer: 404 for other people's objects, 403 for functions your role lacks.
- Log denials, and test that a new route cannot become public by accident.

## Exercise

Close the delete hole above: `deleteDoc` must refuse a document that is not the caller's (answer 404, like `getDoc`), and a test must show that carol, an admin of `acme`, gets 404 when she deletes bob's `globex` document. Then decide what an admin should be allowed to do inside her own tenant, and make the rule tenant-aware.

## What's next

"CSRF, CORS and security headers" asks the next question: whether a request that arrives with valid credentials really came from the user's own page.
