+++
date = '2027-03-29T10:00:00+03:30'
draft = false
title = 'Sessions or JWT?'
description = 'Sessions or JWT in Go: cookie flags, instant logout, a readable JWT payload, tampering, alg none, revocation and a CSRF token, with real output.'
contentType = 'engineering'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "sessions", "jwt", "cookies", "csrf", "authentication", "go"]
cover = { image = "/images/covers/sec-sessions-vs-jwt.png", alt = "Sessions or JWT?", hiddenInSingle = true }
+++

You log out of an app. Does the cookie or token you used a minute ago still work? It depends on what the server remembers about you. With a server-side {{< term "session" "session" >}}, logout is immediate, because the server deletes its record and the cookie in your browser now points at nothing. With a {{< term "jwt" "JWT" >}}, the server kept no record at all, so there is nothing for it to delete, and the token stays valid until it expires.

That difference drives the whole choice, and it fits in two sentences. In a session, the server remembers who you are, and your browser only carries an opaque ID. In a JWT, the client carries signed claims about who it is, and the server remembers nothing. Everything else in this post follows from that. It is the first decision after a login succeeds, where [Storing passwords safely: argon2 and bcrypt](/posts/sec-password-hashing/) ended. The setting is a small orders-style API like the one in [Building an API with net/http in Go](/posts/go-http-api-stdlib/). HttpOnly and CSP come from [Injection and XSS](/posts/sec-injection-xss/).

> Defensive only. A tiny Go program (go.mod says Go 1.25; I re-ran it with Go 1.27) with `github.com/golang-jwt/jwt/v5` v5.2.1, listening on 127.0.0.1 and used only by me with `curl`. The secret in it is a throwaway. **I did not test in a browser**; I only looked at headers. It is a separate demo, not a continuation of an earlier one.

## Server-side session

First the model where the server remembers. On login the server creates a random ID, stores `id -> user` in a table, and gives the browser the ID in a cookie. On each later request the browser sends the cookie back, and the server looks the ID up. The ID means nothing by itself; it is only a key.

In the demo I create 16 random bytes with `crypto/rand`, hex-encode them (that is 128 bits of randomness, so nobody can guess another user's ID) and keep the map in memory:

```go
http.SetCookie(w, &http.Cookie{Name: "sid", Value: id, Path: "/",
	MaxAge: 3600, HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode})
```

`curl -i` shows the response header (the ID is replaced with `<id>`; it is random each time):

```
HTTP/1.1 200 OK
Set-Cookie: sid=<id>; Path=/; Max-Age=3600; HttpOnly; Secure; SameSite=Lax
```

The ID was 32 hex characters. The flags after it are what protect the cookie:

- {{< term "httponly" "HttpOnly" >}} hides the cookie from JavaScript on the page, so an XSS bug cannot read it.
- `Secure` means the browser only sends it over HTTPS.
- {{< term "samesite" "SameSite" >}}`=Lax` limits when the browser attaches it to requests that start on other sites.
- `Max-Age=3600` makes it expire in an hour.

Note: browsers may refuse to store a `Secure` cookie that arrives over plain http (some make an exception for localhost). I only inspected the header, and I sent the cookie by hand with `-H "Cookie: ..."`.

Now the point of the design. Logout deletes the map entry, so revocation is immediate. The demo logs in, uses the cookie, logs out, and uses the same cookie again:

```
GET /me      -> hello alice [200]
POST /logout -> logged out  [200]
GET /me      -> unauthorized [401]
```

The same cookie works until logout and fails right after, because the server no longer knows that ID. The cost of this model: every request needs a lookup, and with several servers the store must be shared (a database or a cache). My map would vanish on restart.

## JWT

The other model moves the memory to the client. A JWT is a string of three base64url parts separated by dots: a header, a payload of claims (facts such as who the user is and when the token expires), and a signature. The server signs the first two parts with a secret key. Later it can check the signature and trust the claims without looking anything up.

The demo signs a token with HS256 (HMAC with SHA-256) and decodes the first two parts. The `exp` value is a Unix timestamp that depends on when you run it:

```
parts: 3
header: {"alg":"HS256","typ":"JWT"}
payload: {"exp":1793817402,"role":"user","sub":"alice"}
signature bytes: 32
```

`alg` says how it was signed, `sub` is the user, `role` is a claim I added, and `exp` is the expiry time. The signature is 32 bytes, the size of a SHA-256 output. Notice that I could read the payload without knowing any key. A JWT is signed, **not encrypted**: anyone holding the token can read it, so never put secrets in it. The signature only detects changes. To see that, I changed `role` to `admin`, kept the old signature, and verified both tokens:

```
verify original: <nil>
verify tampered: token signature is invalid: signature is invalid
```

The original verifies (`<nil>` means no error). The edited one is rejected, because the signature was computed over the old payload.

## alg none and algorithm confusion

The header carries an `alg` field, and that is a trap. Some older JWT libraries were known to trust the `alg` in the token itself, so an attacker could pick `none` (no signature at all) or switch to a different algorithm family. The defence is that the server decides, not the token. My verifier pins the algorithm and requires an `exp`:

```go
jwt.Parse(tok, keyFunc, jwt.WithValidMethods([]string{"HS256"}), jwt.WithExpirationRequired())
```

I built four bad tokens against my own verifier: one with `alg=none`, one signed with HS512 using the same secret, an expired one, and one without `exp`. All four were refused:

```
verify alg=none: token signature is invalid: signing method none is invalid
verify alg=HS512: token signature is invalid: signing method HS512 is invalid
verify expired: token has invalid claims: token is expired
verify no exp: token has invalid claims: token is missing required claim: exp claim is required
```

I did not test an RS256-to-HS256 confusion attack. With the algorithm pinned it should be rejected by the same rule, but that is reasoning, not a run.

## The revocation problem

Now the other half of the opening. After a "logout" the JWT is still fine, because the server kept nothing. The demo's logout endpoint can only ask the client to throw the token away, and the client could just as well keep it:

```
POST /jwt/logout        -> logged out (client discards token)
GET  /jwt/me            -> hello alice [200]
```

The second line is the problem: the same token is still accepted after logout. There are two usual answers. One is a short `exp` (minutes) plus a refresh token that you can revoke. The other is a denylist of token IDs (the `jti` claim) that the server checks. I tried the denylist: logout adds the token's `jti` to it, and the check runs on every request.

```
POST /jwt/logout?denylist=1
GET  /jwt/me            -> unauthorized: revoked [401]
```

Now the token is rejected. But look at what we did: the server stores state and looks it up on every request, which is a session with extra steps. This is the real trade-off. A pure JWT scales without a shared store but cannot be revoked early; the moment you add revocation, you have rebuilt part of a session.

## CSRF

One more risk comes with cookies. Browsers attach cookies automatically, so another website can make your browser send a state-changing POST to ours, using your logged-in cookie. This is {{< term "csrf" "CSRF" >}}. `SameSite=Lax` helps, and a per-session token that must be sent in a header is a second layer. The demo's session holds a random CSRF value; `/csrf` returns it to the logged-in client, and `/transfer` requires it in `X-CSRF-Token`. Without the token the request is rejected; with it, accepted:

```
POST /transfer (no token)       -> csrf token missing or wrong [403]
POST /transfer (X-CSRF-Token)   -> transfer accepted [200]
```

The server compares the token with `subtle.ConstantTimeCompare`, as the password post did for hashes. CSRF did not happen in a real browser here; this only shows the server-side check.

## Where to keep a token (opinion)

This part is my opinion, not a measurement:

- **In a cookie (HttpOnly):** XSS cannot read it, but you need SameSite and CSRF defences.
- **In localStorage or JavaScript memory, sent as a Bearer header:** no CSRF, but any XSS bug can read the token.
- **My view:** for a classic web app, a cookie session is the simpler safe default. JWTs fit service-to-service calls, or short-lived tokens passed across systems.

## Easy ways to get it wrong

- **Do not put secrets, or data you may need to revoke, in the payload.** Anyone holding the token can read it, and you cannot edit it later.
- **Rotate the session ID on login.** This protects against session fixation, where an attacker plants a known ID before the user logs in. I did not demo it.
- **Keep the HS256 secret long and random.** A weak one can be guessed offline from a single token.
- **Always check `exp`, and pin the algorithm.**
- **Never log full tokens or session IDs.** A log is a place where they leak.

## What's next

The next post is "OAuth2 and OIDC". Here we looked at what the server keeps after a login; the next one asks who performs the login in the first place.
