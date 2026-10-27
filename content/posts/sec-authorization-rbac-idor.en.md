+++
date = '2027-04-09T10:00:00+03:30'
draft = false
title = 'Authorization: RBAC and IDOR'
description = 'Authorization in Go on localhost: RBAC permissions, IDOR fixed with ownership checks and 404s, role escalation by mass assignment, and a route test.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "authorization", "rbac", "idor", "go"]
cover = { image = "/images/covers/sec-authorization-rbac-idor.png", alt = "Authorization: RBAC and IDOR", hiddenInSingle = true }
+++

The previous post, [OAuth2 and OIDC](/posts/sec-oauth2-oidc/), ended with a token that says who the caller is and what scopes it has. That is {{< term "authorization" "authorization" >}}'s input, not its answer: the server still decides, per function and per object, what this caller may do. I showed {{< term "idor" "IDOR" >}} briefly in [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/); here I go deeper, with roles, a mass-assignment bug and a test that guards every route. The API style is [net/http from earlier](/posts/go-http-api-stdlib/).

> Defensive only. One small Go 1.26 program on `127.0.0.1`, in-memory data, my own code. Authentication is simplified to fixed tokens (`tok-alice`, `tok-bob`, `tok-carol`) so the focus stays on authorization. A `-mode vuln|fixed` flag builds each version. Users: alice (viewer), bob (editor, another tenant), carol (admin). Documents: 1 is alice's, 2 is bob's.

## 401, 403 or 404

- **401**: I do not know who you are. No or bad token.
- **403**: I know you, and you may not do this. It also tells you the thing exists.
- **404**: used for objects of other users, so a stranger cannot tell "not yours" from "not there".

## The vulnerable version

Alice (a viewer) calls the vulnerable build:

```
GET /documents/2 (bob's) -> {"id":2,"owner":"bob","title":"bob secret"} [200]
DELETE /documents/2      -> [204]
GET /admin/users         -> [{"name":"alice",...,"role":"viewer"},{"name":"bob",...},{"name":"carol",...}] [200]
PATCH /users/me  {"name":"alice","role":"admin"} -> {"name":"alice","tenant":"acme","role":"admin"} [200]
```

Four different holes. The first is object-level (alice reads bob's document); the second and third are function-level (a viewer deletes, a viewer lists admin data); the fourth is {{< term "mass-assignment" "mass assignment" >}}: the handler decodes the JSON straight into the `User` struct, so the client chose its own role. As far as I remember, the OWASP API Security list names the first two "Broken Object Level Authorization" and "Broken Function Level Authorization", but I did not re-check the current edition.

## The fixes

**Object level.** Ownership is part of the lookup, and the answer for someone else's object is 404:

```go
if d == nil || d.Owner != u.Name {
    http.Error(w, "not found", 404)
    return
}
```

With a database, the same idea is `WHERE id = $1 AND owner_id = $2`: one query, no separate "fetch then check" step to forget. I used a map here and did not run it against Postgres.

**Function level.** Roles map to permissions, and a route declares what it needs:

```go
var perms = map[string][]string{
    "viewer": {"doc:read"},
    "editor": {"doc:read", "doc:write"},
    "admin":  {"doc:read", "doc:write", "doc:delete", "users:read"},
}
a.protect("DELETE /documents/{id}", "doc:delete", a.deleteDoc)
```

The code checks the permission, never the role name, which is the point of {{< term "rbac" "RBAC" >}}. The wrapper does the 401 check, then the permission check.

**Mass assignment.** Decode into an explicit allow-list type:

```go
var in struct {
    Name string `json:"name"`
}
json.NewDecoder(r.Body).Decode(&in)
```

Same alice, fixed build:

```
GET /documents/2         -> not found [404]
GET /documents/99        -> not found [404]
DELETE /documents/2      -> forbidden [403]
GET /admin/users         -> forbidden [403]
PATCH /users/me {"name":"alice","role":"admin"} -> {"name":"alice","tenant":"acme","role":"viewer"} [200]
GET /documents/1 (hers)  -> {"id":1,"owner":"alice","title":"alice plan"} [200]
```

The document that exists (2) and the one that does not (99) now look identical. The extra `role` field is ignored. Server log lines for the denials:

```
level=WARN msg="authz denied" user=alice doc=2 owner=bob
level=WARN msg="authz denied" user=alice role=viewer need=doc:delete route="DELETE /documents/{id}"
level=WARN msg="authz denied" user=alice role=viewer need=users:read route="GET /admin/users"
```

Log every denial with who, what and which rule ([structured logging](/posts/go-config-logging-errors/) makes this searchable). A burst of 404s and 403s from one user is how enumeration looks. Do not log tokens.

## Deny by default, and a test that enforces it

The design rule is {{< term "deny-by-default" "deny by default" >}}: every route needs a token unless it is explicitly listed as public. A test makes the rule survive future edits. Routes are registered through two helpers that record the pattern, and the test calls each one without a token:

```go
var publicRoutes = map[string]bool{"GET /healthz": true}
// for every registered route not in publicRoutes: expect 401
```

To see it work I temporarily added an unprotected `GET /debug/vars` via `public(...)`:

```
routes_test.go:26: GET /debug/vars answered 200 without a token, want 401
--- FAIL: TestEveryRouteRequiresAuth (0.00s)
    --- FAIL: TestEveryRouteRequiresAuth/GET_/debug/vars (0.00s)
FAIL
```

I removed the route and the suite passes again (`TestViewerCannotDelete` checks a 403 too). A limit: this catches routes registered through my helpers, not a handler wired onto the mux by hand.

## Beyond roles

RBAC gets awkward when rules depend on attributes (owner, tenant, time) or on relationships (a member of a folder's team). Attribute-based (ABAC) and relationship-based (ReBAC) models cover those. I only mention them; I did not run either.

## A few things to watch

- Check authorization on the server, for every function and every object. Hiding a button is not a check.
- Take the identity from the verified token, never from an ID in the body or URL.
- Decode into allow-list types; never into your database or domain struct.
- Be consistent: 404 for other people's objects, 403 for functions your role lacks.
- Log denials, and test that new routes cannot be public by accident.

## Exercise

Add an `editor` rule: editors may update documents of their own tenant. Add a second tenant-aware test where carol (admin, acme) must get 404 for bob's globex document.

## What's next

The next post is CSRF, CORS and security headers.
