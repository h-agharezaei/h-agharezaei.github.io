+++
date = '2027-04-02T10:00:00+03:30'
draft = false
title = 'OAuth2 and OIDC'
description = 'OAuth2 and OIDC in Go on localhost: Authorization Code flow with PKCE, state, ID token validation with JWKS, scopes and refresh rotation, with real output.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "oauth2", "oidc", "pkce", "jwt", "go"]
cover = { image = "/images/covers/sec-oauth2-oidc.png", alt = "OAuth2 and OIDC", hiddenInSingle = true }
+++

Think about an orders app that wants to show you your orders from another service. The easy way is to ask for your username and password there and log in on your behalf. That works, and it is a terrible idea: the app now holds your full password, it can do anything you can, and the only way to take its access away is to change your password. "Sign in with X" buttons exist to avoid exactly this. The app never sees your password; it receives a small, limited, revocable token instead.

The protocol behind this is {{< term "oauth2" "OAuth2" >}}. The idea in one sentence: the user proves who they are to a server they already trust, and that server hands the app a token that says "this app may do these specific things for this user". OAuth2 is about **authorization**, what a token may do. It does not say who logged in. {{< term "oidc" "OpenID Connect" >}} (OIDC) is a thin layer on top that adds the missing piece: an **ID token**, which tells the app who logged in. That is **authentication**.

The previous post, [Sessions or JWT?](/posts/sec-sessions-vs-jwt/), was about what a server keeps after a login. This one is about who performs the login when it is not your own server. I will walk through the whole flow against a toy implementation, and for each step show what the right behaviour is and what a wrong request looks like. The API at the end is the orders API idea from [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Defensive only. Everything ran on `127.0.0.1` in one Go program (Go 1.27.3, macOS arm64, standard library only; the demo's `go.mod` says 1.26): an authorization server, a resource server and a client. Tokens are RS256 {{< term "jwt" "JWT" >}}s that I signed by hand with `crypto/rsa`. There is no real identity provider, no browser and no third-party account. The "user" is already logged in and consents automatically, and the client's callback is a printed `302` response rather than a real listener. Random values (state, nonce, codes, tokens, the PKCE challenge) are different on every run; the outputs below are from one single run.

## Who is who

Four roles appear in every OAuth2 story, and it helps to name them before any code:

- The **user** (the resource owner) owns the data: Alice and her orders.
- The **client** is the app that wants access: here `orders-web`.
- The **authorization server** knows Alice, checks her login and issues tokens.
- The **resource server** is the API that holds the orders and accepts tokens.

The flow we use is the {{< term "authorization-code-flow" "Authorization Code flow" >}}. The client sends Alice's browser to the authorization server. Alice logs in there. The authorization server sends the browser back to the client with a short-lived **code**. Then the client, directly and not through the browser, swaps the code for tokens. The browser only ever carries a code, never a token. That matters because URLs end up in browser history and logs, while the code swap happens on a direct connection.

## Step 1: the authorization request

First the client sends the browser to `/authorize` with a list of parameters. The demo prints them one by one:

```
  response_type          code
  client_id              orders-web
  redirect_uri           http://127.0.0.1:5555/callback
  scope                  openid profile orders:read
  state                  y7FOdbYUeHr2wiig
  nonce                  ClK8-HVEFlLlrCsJ
  code_challenge         w-6XYQt_NIcmO5PWi7-2y1Tprfe31qIFJ7Gzze-LM4c
  code_challenge_method  S256
```

What each one means:

- `response_type=code` says "I want the code flow".
- `client_id` says which app is asking.
- `redirect_uri` is where the browser should be sent back. The server must know this address in advance and compare it exactly. If the check were loose, a crafted link could send the code to someone else's address. (In the demo nothing listens on port 5555; we just read the redirect.)
- `scope` is the list of things the client asks for. `orders:read` is "read orders". `openid` is the word that turns this into an OIDC login and gets us an ID token. `profile` asks for basic profile data.
- `state` is a random value the client invents and expects to get back unchanged. More on it below.
- `nonce` is another random value, which the server copies into the ID token. More on it below too.
- `code_challenge` and `code_challenge_method` belong to {{< term "pkce" "PKCE" >}}, also below.

My demo server insists on PKCE with `S256` and refuses an authorization request without it. That is a choice of this demo; RFC 9700, the current security best practice for OAuth 2.0, says public clients must use PKCE and authorization servers must support it.

## Step 2: the redirect back, and what `state` is for

The authorization server answers with a redirect to the client's `redirect_uri`, carrying a short-lived code and the same `state`:

```
302 Location: http://127.0.0.1:5555/callback?code=HS3Ow0BUavIsfJqRHr7bpQ&state=y7FOdbYUeHr2wiig
state matches what we sent: true
callback with state=attacker-chosen accepted: false -> client drops it, never exchanges the code
```

A `302` is a redirect: the browser goes to the address in `Location`. Now the question is why the client needs `state` at all. Imagine an attacker who starts a login flow with their own account, stops at the callback, and tricks your browser into opening that callback link. Without a check, the client would finish the flow and attach the attacker's account to your session. That is a {{< term "csrf" "CSRF" >}} on the login: a request your browser sends that you did not intend. The cure is simple. The client stores the `state` it sent, in this browser, and compares it with the one on the callback. If it differs, the client throws the callback away and never uses the code.

The last line of that output is a plain string comparison in my demo, not a forged request from a real browser. RFC 9700 says clients must defend against CSRF, either with PKCE or with one-time tokens in `state`.

## Step 3: PKCE and a stolen code

The code is only a short-lived ticket, but suppose it leaks anyway: it was in a log, or a malicious app on the same device saw the redirect. PKCE (Proof Key for Code Exchange) makes a leaked code useless.

Before the flow starts, the client invents a random secret called the **verifier**. In step 1 it sent only a fingerprint of it, the **challenge**, which is `base64url(sha256(verifier))`. When the client later swaps the code for tokens, it sends the verifier itself. The server hashes it and compares with the challenge it stored. Someone who stole only the code has no verifier, and cannot guess it from the challenge.

First I checked my challenge computation against the worked example from RFC 7636 (the PKCE specification):

```
verifier   dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
challenge  E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM  matches RFC example: true
```

Then the demo plays the thief with the code from step 2, and then the real owner:

```
thief, wrong verifier: 400 invalid_grant - PKCE verification failed
owner, right verifier, after the failed try: 400 invalid_grant - unknown or already used code
```

The thief gets `400 invalid_grant` because the verifier does not match. The second line shows a design choice of my server: it burns the code on any failed attempt, so the real owner must start a new flow. The code is single use either way. The standard rules out reuse, and what happens after a failed attempt is up to the server.

One more rule that follows: never put a secret in a URL. The code is safe enough there because it is short-lived and useless alone. A token or a verifier in a URL would end up in logs and history.

## Step 4: swapping the code for tokens

Now a fresh authorization, and the real exchange. The client sends the code and the verifier to `/token` directly:

```
POST /token  grant_type=authorization_code code=yXGZdohLuZIlVIoPUqNjPg code_verifier=FrJZv68hLfzPElLjh4kQ...kTjnpQ
status 200
  token_type     Bearer
  expires_in     300
  scope          openid profile orders:read
  access_token   eyJhbGciOiJSUzI1NiIs...9X62Dw
  id_token       eyJhbGciOiJSUzI1NiIs...AyfO-Q
  refresh_token  _IAdvsu67RynDgwo
code reuse: 400 unknown or already used code
```

The long tokens are shortened by the demo. The response holds three tokens, each with a different job:

- The **access token** is what the client shows to the API. It lives 300 seconds (`expires_in`), which is short on purpose.
- The **ID token** is for the client only. It says who logged in. It is there because we asked for the `openid` scope.
- The **refresh token** lets the client get a new access token later without sending Alice through the login again.

The last line shows that using the same code a second time fails.

## Step 5: validating the ID token

The ID token is a JWT: three base64url parts, header, payload and signature. The payload is only encoded, not encrypted, so anybody can read it. What makes it trustworthy is the signature and the checks the client does. The client downloads the authorization server's public key from `/jwks.json` (a {{< term "jwks" "JWKS" >}}, a JSON list of public keys), verifies the signature, and then checks the claims:

- `iss`: the issuer is the authorization server I expect.
- `aud`: the audience is my own `client_id`, so the token was meant for me.
- `exp`: the token has not expired.
- `nonce`: it equals the value I sent in step 1. This ties the ID token to this login attempt, so an old token cannot be replayed into a new one.

The demo feeds the checker one good token and six bad ones:

```
good               OK sub=alice name=Alice
wrong nonce        REJECT nonce
tampered payload   REJECT bad signature
other signing key  REJECT bad signature
wrong aud          REJECT aud=another-app
expired            REJECT expired
alg=none token: alg not allowed: none
```

Line by line: the good token passes and tells us `sub=alice`, the stable id of the user. A wrong nonce is rejected. A token whose payload was edited no longer matches its signature. A token signed by some other key fails against the published key. A token made for `another-app` is rejected because `aud` is not ours. An expired token is rejected. The last line is a token whose header says `alg: none`, "no signature needed". The checker never trusts the algorithm named by the token. It has a fixed allow-list (only RS256) and refuses everything else.

## Step 6: calling the API

Now the client uses the access token as a {{< term "bearer-token" "bearer token" >}}, which means whoever holds it can use it, sent in an `Authorization: Bearer ...` header:

```
GET  /orders, no token      -> 401 missing bearer token
GET  /orders, Bearer        -> 200 ok GET /orders for sub=alice
POST /orders, Bearer        -> 403 insufficient_scope: need orders:write
GET  /orders, ID token      -> 401 bad iss/aud/exp
GET  /userinfo, Bearer      -> 200 {"name":"Alice","sub":"alice"}
```

No token gives `401`. The token with `orders:read` can read. Creating an order needs `orders:write`, which Alice never granted, so the answer is `403`. The fourth line is the important one: the client's ID token is rejected by the API, because its `aud` is the client and not the orders API. An ID token proves login to the client; it is not a credential for APIs. The last line is the OIDC `userinfo` endpoint, which returns the profile for an access token.

A **scope** is what the user allowed this client to do. A **role** is what the user is allowed to do in your system at all. A request must pass both. The next post is about roles and the checks inside the API.

## Step 7: refresh token rotation

A {{< term "refresh-token" "refresh token" >}} lives long, so it is a juicy target. A common defence is to rotate it: each use returns a new refresh token and invalidates the old one.

```
use rt1: 200 new refresh token: 2LvNOnObhmBiCR6D differs: true
use rt1 again: 400 refresh token reuse detected, family revoked
use rt2 (same family): 400 family revoked
```

The first use works and gives a new token (`rt2`). Using the old `rt1` again is suspicious: either a thief or the real owner holds a stale copy, and the server cannot tell which. So it revokes the whole **family**, every token descended from that login, and the last line shows even the fresh `rt2` no longer works. The real user has to log in again, which is a small price. RFC 9700 asks for refresh tokens of public clients to be sender-constrained or rotated.

## Where OAuth setups go wrong

- **Loose `redirect_uri` matching.** Prefix or wildcard matching lets an attacker steer the code to their own address. RFC 9700 says the server must use exact string matching.
- **The wrong grants.** According to RFC 9700, clients should not use the Implicit grant (it returns the token in the URL) and the Resource Owner Password Credentials grant, where the app collects the password, must not be used at all. Use the code flow with PKCE. I did not run either of those flows.
- **Mixing up the tokens.** Do not use an ID token as an API credential, and do not treat an access token as proof that somebody just logged in.
- **Long-lived access tokens.** Keep them short, and use HTTPS everywhere outside this loopback demo. Without HTTPS anyone on the path can read the code and the tokens.
- **Logging tokens.** Do not log tokens or full callback URLs.
- **What the demo skips.** There is no real login page or consent screen, no client secret, no real browser. I only showed the server-side rules.

## Exercise

Add token revocation: a `/revoke` endpoint that marks a refresh token family as revoked, and a test showing that the next refresh fails.

## What's next

"Authorization: RBAC and IDOR" follows because a valid token only says who the caller is. What that caller may do with each object is still the server's decision.
