+++
date = '2027-04-17T10:00:00+03:30'
draft = false
title = 'CSRF, CORS and security headers'
description = 'CSRF, CORS and security headers in Go on localhost: why CORS does not stop forged writes, allow-list CORS, token and Origin checks, tested headers.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "csrf", "cors", "security-headers", "go"]
cover = { image = "/images/covers/sec-csrf-cors-headers.png", alt = "CSRF, CORS and security headers", hiddenInSingle = true }
+++

The previous post, [Authorization: RBAC and IDOR](/posts/sec-authorization-rbac-idor/), asked what a caller may do. This one asks whether the request really came from the caller's own page. [Sessions or JWT?](/posts/sec-sessions-vs-jwt/) introduced {{< term "csrf" "CSRF" >}} and {{< term "samesite" "SameSite" >}}, and [Injection and XSS](/posts/sec-injection-xss/) introduced {{< term "content-security-policy" "CSP" >}} and `HttpOnly`; I go deeper here, on the server side. The API style is [net/http](/posts/go-http-api-stdlib/).

> Defensive only. One Go 1.26 program on `127.0.0.1:9100`, in-memory data, a fixed session cookie `sid=s-alice`, and a `-mode vuln|fixed` flag. A "foreign origin" is just an `Origin` header I send with curl. **I did not test any browser behavior**; every claim about what a browser does is from the specs, hedged.

## CORS is enforced by browsers, not servers

{{< term "cors" "CORS" >}} tells a browser whether a page from another origin may *read* a response. It does not stop the request being sent. A form-encoded POST is a "simple request": no preflight, cookies attached. In the vulnerable build:

```
$ curl -si -H 'Cookie: sid=s-alice' -H 'Origin: https://evil.test' -d amount=30 /transfer
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: https://evil.test
{"balance":70}
```

The balance went from 100 to 70 on the server. Even with perfect CORS, that write would have happened, so CORS is not a CSRF defense.

## The preflight

A JSON body or a custom header makes the browser first send an {{< term "preflight" "preflight" >}} `OPTIONS` request. My middleware answers it from the allow-list (fixed build, allowed origin):

```
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Origin: https://app.example.test
Access-Control-Max-Age: 600
Vary: Origin
```

An unknown origin gets only `Vary: Origin`, with no `Allow-*` headers, so a browser would refuse the real request. `Vary: Origin` matters because the answer depends on the header; without it a shared cache could serve one origin's answer to another.

## Classic CORS mistakes

- **Reflecting any Origin with credentials.** The vulnerable build above does this. A hostile page could then read authenticated responses.
- **Allowing `null`.** Vulnerable build: `Origin: null` gets `Access-Control-Allow-Origin: null` plus credentials. Sandboxed frames and redirects can send `null`, so it is not a safe identity.
- **A prefix or regex that is too loose.** My matcher test:

```
https://app.example.test               bad=true  good=true
https://app.example.test.evil.test     bad=true  good=false
null                                   bad=false good=false
```

`bad` is `strings.HasPrefix`, which accepts the lookalike; `good` is an exact map lookup. Anchor regexes with `^...$` or, better, do not use them.

- **`*` with credentials.** I fetched the Fetch standard's "CORS check": it accepts `*` only when the credentials mode is not `include`; otherwise the header must equal the request origin exactly, and `Access-Control-Allow-Credentials: true` must be present. So `*` cannot be combined with cookies.

## CSRF defenses, with results

Fixed build, same `/transfer` request. The cookie now carries `SameSite=Lax` (header shown, browser not tested):

```
Set-Cookie: sid=s-alice; Path=/; HttpOnly; SameSite=Lax
```

Server-side checks, from curl:

```
Origin: https://evil.test            -> 403 cross-site request refused
Sec-Fetch-Site: cross-site           -> 403 cross-site request refused
Sec-Fetch-Site: same-origin, no token-> 403 bad csrf token
Sec-Fetch-Site: same-origin + token  -> 200 {"balance":70}
no Origin, no Sec-Fetch-Site         -> 403 cross-site request refused
```

The balance stayed 100 until the valid request. Three layers:

1. **Origin / Sec-Fetch-Site check.** Browsers set these headers and page scripts cannot override them, according to the specs. Requests that carry neither are refused here; that also refuses non-browser clients, so a real API needs another way to authenticate them.
2. **Synchroniser token.** `GET /csrf` returns an HMAC of the session id; `/transfer` requires it as the `csrf` form field.
3. **Double-submit cookie.** `/api/settings` requires the `csrf` cookie to equal the `X-CSRF-Token` header. Missing or wrong header gave 403; matching gave 200. It works because a foreign page cannot read or set your cookies for this site; it is weaker if subdomains are untrusted.

## Security headers

The fixed build adds these to every response (checked with `curl -i`):

| Header | Purpose |
|---|---|
| `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` | load only same-origin resources; forbid framing |
| `Strict-Transport-Security: max-age=31536000; includeSubDomains` | {{< term "hsts" "HSTS" >}}: use HTTPS next time |
| `X-Content-Type-Options: nosniff` | no MIME guessing |
| `Referrer-Policy: strict-origin-when-cross-origin` | send less URL to other sites |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | switch off browser features |
| `Cross-Origin-Opener-Policy: same-origin` | isolate the window from cross-origin openers |

HSTS is, per its spec, ignored when received over plain HTTP, so on my localhost demo it only shows the header; it matters on HTTPS (next post).

A test keeps the headers from regressing: it calls every route plus an unknown path (404) and asserts all six are present. It passes with `go test`; the middleware wraps the whole mux, so error responses are covered too.

## A few things to watch

- CORS controls reading, not sending. Protect writes with tokens or origin checks.
- Allow-list exact origins; add `Vary: Origin`; never reflect, never `null`.
- Do not rely on `SameSite` alone; it is one layer.
- Do not change state on `GET`.
- Headers are defense in depth. They do not fix XSS or missing authorization.

## Exercise

Make `/transfer` accept a JSON body with `X-CSRF-Token` and add a test where a forged `Origin` with a valid token still gets 403.

## What's next

The next post is TLS and x509 certificates in practice.
