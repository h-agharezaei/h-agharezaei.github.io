+++
date = '2027-04-02T10:00:00+03:30'
draft = false
title = 'OAuth2 and OIDC'
description = 'OAuth2 and OIDC in Go on localhost: Authorization Code flow with PKCE, state, ID token validation with JWKS, scopes and refresh rotation, with real output.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "oauth2", "oidc", "pkce", "jwt", "go"]
cover = { image = "/images/covers/sec-oauth2-oidc.png", alt = "OAuth2 and OIDC", hiddenInSingle = true }
+++

The previous post, [Sessions or JWT?](/posts/sec-sessions-vs-jwt/), was about what a server keeps after login. Here the question is who does the login. "Sign in with X" and "let this app read my orders" are both {{< term "oauth2" "OAuth2" >}} and {{< term "oidc" "OpenID Connect" >}}. The short version: OAuth2 is **authorization** (what may this token do), and OIDC adds **authentication** (who logged in) with an ID token. The API on the resource side is the orders API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Defensive only. Everything ran on `127.0.0.1` in one Go 1.26 stdlib program: an authorization server, a resource server and a client. Tokens are RS256 JWTs I signed by hand with `crypto/rsa`. No real identity provider, no browser, no third-party account. The "user" is logged in and consents automatically, and the client's callback is a printed 302, not a real listener. It is a separate demo.

## The Authorization Code flow with PKCE

The client sends the browser to `/authorize`. I computed the {{< term "pkce" "PKCE" >}} challenge with `base64url(sha256(verifier))` and checked it against the example in RFC 7636:

```
verifier   dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
challenge  E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM  matches RFC example: true
```

The real request, parameter by parameter:

```
  response_type          code
  client_id              orders-web
  redirect_uri           http://127.0.0.1:5555/callback
  scope                  openid profile orders:read
  state                  p84e_dRe79Q8wp1b
  nonce                  NL5oWAIUD41i8noq
  code_challenge         1ISr_nQK-v-0F1yoMU-Gn9D1j-j-l8_I6Ro1EJTgn1g
  code_challenge_method  S256
```

The server answers with a redirect that carries a short-lived code and the same state. This is the {{< term "authorization-code-flow" "Authorization Code flow" >}}: the browser carries only a code, never a token.

```
302 Location: http://127.0.0.1:5555/callback?code=Zz-fQ1CTqGbvgNXeaY2f7g&state=p84e_dRe79Q8wp1b
```

## What state prevents

`state` ties the callback to the request this browser started. Without it an attacker can make your browser finish a flow the attacker started, which is a {{< term "csrf" "CSRF" >}} on the login. The client compares and drops a mismatch before using the code:

```
state matches what we sent: true
callback with state=attacker-chosen accepted: false -> client drops it, never exchanges the code
```

That second line is a plain comparison in my demo, not a real forged browser request.

## What PKCE prevents

Suppose a code leaks (a log, a malicious app on the same device). Without the verifier it is useless:

```
thief, wrong verifier: 400 invalid_grant - PKCE verification failed
owner, right verifier, after the failed try: 400 invalid_grant - unknown or already used code
```

My server burns the code on any failed attempt, so the owner must start again. That is a design choice; the code is single use either way. Never put secrets in the URL: the code is short-lived and useless alone, but a token or a verifier in a URL ends up in logs and history.

## Tokens, and validating the ID token

```
POST /token  grant_type=authorization_code code=n9yU0uooh8YRQbKfml7Wew code_verifier=W4gzTNnQL1wPyM6MGnLo...y9dRAQ
  token_type     Bearer
  expires_in     300
  scope          openid profile orders:read
  access_token   eyJhbGciOiJSUzI1NiIs...kneOSA
  id_token       eyJhbGciOiJSUzI1NiIs...gnMBVA
  refresh_token  v7QR2NLJy8l4-0tw
```

The client fetches the public key from `/jwks.json` ({{< term "jwks" "JWKS" >}}) and checks the signature, then `iss`, `aud` (must be my `client_id`), `exp` and `nonce`:

```
good               OK sub=alice name=Alice
wrong nonce        REJECT nonce
tampered payload   REJECT bad signature
other signing key  REJECT bad signature
wrong aud          REJECT aud=another-app
expired            REJECT expired
alg=none token:    alg not allowed: none
```

Never accept the algorithm the token asks for; fix an allow-list. The {{< term "jwt" "JWT" >}} payload is only encoded, so the checks are what make it trustworthy.

## Access token, scopes and roles

The client calls the API with a {{< term "bearer-token" "bearer token" >}}:

```
GET  /orders, no token      -> 401 missing bearer token
GET  /orders, Bearer        -> 200 ok GET /orders for sub=alice
POST /orders, Bearer        -> 403 insufficient_scope: need orders:write
GET  /orders, ID token      -> 401 bad iss/aud/exp
```

A **scope** is what the user allowed this client to do; a **role** is what the user is allowed to do in your system. A request needs both. An ID token is for the client, not the API: the API rejects it because its `aud` is wrong. Roles come in the next post.

## Refresh token rotation

A {{< term "refresh-token" "refresh token" >}} is long-lived, so each use returns a new one and kills the old:

```
use rt1: 200 new refresh token: QdxTjk6f54VwJgIb differs: true
use rt1 again: 400 refresh token reuse detected, family revoked
use rt2 (same family): 400 family revoked
```

If an old token reappears, either the thief or the owner is using it, so the server revokes the whole family.

## A few things to watch

- Match `redirect_uri` exactly on the server; prefix or wildcard matching invites open-redirect problems.
- According to RFC 9700 (OAuth 2.0 security best current practice, which I checked for these two points), clients should not use the Implicit grant, and the Resource Owner Password Credentials grant must not be used. Use the code flow with PKCE. I did not run either discouraged flow.
- Do not use an ID token as an API credential, or an access token as proof of login.
- Keep access tokens short; use HTTPS everywhere outside this loopback demo.
- Do not log tokens or full callback URLs.

## Exercise

Add token revocation: a `/revoke` endpoint that marks a refresh token family revoked, and a test that the next refresh fails.

## What's next

The next post is Authorization: RBAC and IDOR.
