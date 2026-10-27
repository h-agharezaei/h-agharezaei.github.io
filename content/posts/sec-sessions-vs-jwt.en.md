+++
date = '2027-03-29T10:00:00+03:30'
draft = false
title = 'Sessions or JWT?'
description = 'Sessions or JWT in Go: cookie flags, instant logout, a readable JWT payload, tampering, alg none, revocation and a CSRF token, with real output.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "sessions", "jwt", "cookies", "csrf", "authentication", "go"]
cover = { image = "/images/covers/sec-sessions-vs-jwt.png", alt = "Sessions or JWT?", hiddenInSingle = true }
+++

The previous post, [Storing passwords safely: argon2 and bcrypt](/posts/sec-password-hashing/), ended at the moment a login succeeds. Now the server must remember who you are for the next request. There are two common answers: a {{< term "session" "session" >}} (the server remembers) and a {{< term "jwt" "JWT" >}} (the client carries signed claims). The setting is a small orders-style API like the one in [Building an API with net/http in Go](/posts/go-http-api-stdlib/). HttpOnly and CSP come from [Injection and XSS](/posts/sec-injection-xss/).

> Defensive only. A tiny Go 1.26 program with `github.com/golang-jwt/jwt/v5` v5.2.1, listening on 127.0.0.1 and attacked only by me with `curl`. **I did not test in a browser**; I only looked at headers. It is a separate demo, not a continuation of an earlier one.

## Server-side session

On login I create 16 random bytes with `crypto/rand`, hex-encode them (128 bits) and keep `id -> user` in an in-memory map:

```go
http.SetCookie(w, &http.Cookie{Name: "sid", Value: id, Path: "/",
	MaxAge: 3600, HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode})
```

`curl -i` shows (id replaced):

```
HTTP/1.1 200 OK
Set-Cookie: sid=<id>; Path=/; Max-Age=3600; HttpOnly; Secure; SameSite=Lax
```

The id was 32 hex characters. {{< term "httponly" "HttpOnly" >}} hides the cookie from page JavaScript, `Secure` means HTTPS only, and {{< term "samesite" "SameSite" >}}=Lax limits cross-site sending. Note: browsers may not store a `Secure` cookie from plain http (some make an exception for localhost). I only inspected the header, and I sent the cookie manually with `-H`.

Logout deletes the map entry, so revocation is immediate:

```
GET /me      -> hello alice [200]
POST /logout -> logged out  [200]
GET /me      -> unauthorized [401]
```

The cost: every request needs a lookup, and with several servers the store must be shared (a database or cache). My map would vanish on restart.

## JWT

A JWT is three base64url parts. I decoded the first two from a token I signed with HS256:

```
parts: 3
header: {"alg":"HS256","typ":"JWT"}
payload: {"exp":1793085367,"role":"user","sub":"alice"}
signature bytes: 32
```

It is signed, **not encrypted**: anyone holding the token reads the payload, so never put secrets in it. The signature only detects changes. I changed `role` to `admin`, kept the old signature, and verified:

```
verify original: <nil>
verify tampered: token signature is invalid: signature is invalid
```

## alg none and algorithm confusion

Old libraries trusted the `alg` field in the token itself, so an attacker could pick `none` (no signature) or switch algorithm families. The fix is that the server decides. My verifier pins it and requires `exp`:

```go
jwt.Parse(tok, keyFunc, jwt.WithValidMethods([]string{"HS256"}), jwt.WithExpirationRequired())
```

I built tokens against my own verifier:

```
verify alg=none:  token signature is invalid: signing method none is invalid
verify alg=HS512: token signature is invalid: signing method HS512 is invalid
verify expired:   token has invalid claims: token is expired
verify no exp:    token has invalid claims: token is missing required claim: exp claim is required
```

I did not test an RS256-to-HS256 confusion attack; with pinning it is the same rejection by design, but that is reasoning.

## The revocation problem

After "logout" the token is still fine, because the server kept nothing:

```
POST /jwt/logout        -> logged out (client discards token)
GET  /jwt/me            -> hello alice [200]
```

Options: short `exp` (minutes) plus a refresh token you can revoke, or a denylist of token ids (`jti`). I tried the denylist:

```
POST /jwt/logout?denylist=1
GET  /jwt/me            -> unauthorized: revoked [401]
```

Notice what happened: the server now stores state and looks it up on every request, which is a session with extra steps.

## CSRF

Cookies are attached automatically, so another site can make the browser send a state-changing POST. SameSite=Lax helps, and a per-session token in a header is a second layer. With the token missing the request is rejected; with it, accepted:

```
POST /transfer (no token)       -> csrf token missing or wrong [403]
POST /transfer (X-CSRF-Token)   -> transfer accepted [200]
```

The compare uses `subtle.ConstantTimeCompare`, as in the previous post. {{< term "csrf" "CSRF" >}} did not happen in a real browser here; this only shows the server check.

## Where to keep a token (opinion)

- Cookie (HttpOnly): XSS cannot read it, but you need SameSite and CSRF defences.
- localStorage or JS memory with a Bearer header: no CSRF, but any XSS can read the token.
- My opinion: for a classic web app, a cookie session is the simpler safe default. JWTs fit service-to-service calls or short-lived tokens across systems.

## A few things to watch

- Do not put secrets or data you need to revoke in the payload.
- Rotate the session id on login (against session fixation); I did not demo it.
- Keep the HS256 secret long and random; a weak one can be guessed offline.
- Always check `exp`, and pin the algorithm.
- Never log full tokens or session ids.

## Exercise

Add a refresh token: a 5-minute JWT plus a random refresh id stored server-side. Write a test that revoking the refresh id stops new access tokens, and measure how long the old access token still works.

## What's next

The next post is OAuth2 and OIDC.
