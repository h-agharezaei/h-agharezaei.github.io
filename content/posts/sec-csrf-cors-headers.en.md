+++
date = '2027-04-17T10:00:00+03:30'
draft = false
title = 'CSRF, CORS and security headers'
description = 'CSRF, CORS and security headers in Go on localhost: why CORS does not stop forged writes, allow-list CORS, token and Origin checks, tested headers.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "csrf", "cors", "security-headers", "go"]
cover = { image = "/images/covers/sec-csrf-cors-headers.png", alt = "CSRF, CORS and security headers", hiddenInSingle = true }
+++

Picture Alice, logged in to her bank in one browser tab. In another tab she opens a harmless-looking page. That page contains a hidden form that submits to `https://bank.example/transfer`, and a script that submits it as soon as the page loads. Her browser does what browsers do: it sends the request and attaches her bank cookie, because the request is going to the bank. The bank sees a valid session and moves the money. Alice never clicked anything.

This is {{< term "csrf" "CSRF" >}} (cross-site request forgery), and it is one reason that knowing who the caller is and what they may do ([Authorization: RBAC and IDOR](/posts/sec-authorization-rbac-idor/)) is not enough. The request must also really come from the caller's own page. [Sessions or JWT?](/posts/sec-sessions-vs-jwt/) mentioned CSRF and the {{< term "samesite" "SameSite" >}} cookie attribute, and [Injection and XSS](/posts/sec-injection-xss/) introduced {{< term "content-security-policy" "CSP" >}} and `HttpOnly`. In this post I take the server side: how to refuse such a request, how {{< term "cors" "CORS" >}} fits in (it is often confused with CSRF defence, and it is not one), and which response headers add a further layer. The API style is the [net/http one from earlier](/posts/go-http-api-stdlib/).

> Defensive only. One Go program on loopback with in-memory data, a fixed session cookie `sid=s-alice`, and a `-mode vuln|fixed` flag (Go 1.27.3 on macOS arm64; the demo's `go.mod` says 1.26). The demo listens on `127.0.0.1:9100` by default; I ran it on a random free port instead. A "foreign origin" here is just an `Origin` header that I send with `curl`. **I did not test any browser behaviour**: every claim about what a browser does comes from the specs or MDN and is hedged.

## What an origin is, and what the browser blocks

An **origin** is the triple scheme, host and port: `https://app.example.test` and `https://app.example.test:8443` are different origins. The browser's **same-origin policy** has a rule that surprises people: a page from one origin may *send* a request to another origin, but may not *read* the answer. CORS exists to relax the second half. A server can say "this other origin may read my responses", with `Access-Control-Allow-*` headers.

So two different problems get mixed up:

- **Reading** across origins is controlled by CORS. The enemy is a hostile page that reads Alice's private data.
- **Sending** across origins is not blocked by CORS at all. The enemy is a hostile page that makes Alice's browser do something. That is CSRF.

Let me show the second one first, on the vulnerable build.

## CORS does not stop the request

A form-encoded `POST` is what the specs call a "simple request": no preflight, and the browser sends it straight away (MDN lists the methods `GET`, `HEAD`, `POST` and the content types `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain` as simple). In a real browser the cookie only gets attached if SameSite allows it, and MDN notes that some browsers treat a cookie without `SameSite` as `Lax` by default, so a real attack depends on that. I did not test it. What I can show is what the server does when such a request arrives, with an `Origin` header from a foreign site and Alice's cookie:

```
$ curl -si -H 'Cookie: sid=s-alice' -H 'Origin: https://evil.test' -d amount=30 .../transfer
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: https://evil.test
Vary: Origin
Content-Type: text/plain; charset=utf-8

{"balance":70}
```

(I left out the `Date` and `Content-Length` lines.) The balance on the server went from 100 to 70. The vulnerable build also echoes the foreign origin back in `Access-Control-Allow-Origin` and allows credentials, which would let that page read the answer as well. But even a perfect CORS configuration would not have stopped the transfer itself: CORS is not a CSRF defence.

## The preflight

If a request is not "simple", for example a JSON body or a custom header such as `X-CSRF-Token`, the browser first sends a {{< term "preflight" "preflight" >}}: an `OPTIONS` request asking "would you accept this?". Only if the answer allows it does the real request follow. My middleware answers from an allow-list. For the allowed origin in the fixed build, the preflight response carries these CORS headers (the real response also has the six security headers shown further down, which I leave out here):

```
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Origin: https://app.example.test
Access-Control-Max-Age: 600
Vary: Origin
```

For an unknown origin (`https://evil.test`), and also for `null`, the answer has only `Vary: Origin` and no `Access-Control-*` headers, so a browser would refuse to send the real request. `Vary: Origin` is there because the answer depends on the `Origin` header; without it a shared cache could hand one origin's answer to another. MDN says a server that answers with a single, dynamically chosen origin should also send `Vary: Origin`.

## Classic CORS mistakes

- **Reflecting any `Origin` and allowing credentials.** The vulnerable build above does exactly this. A hostile page could then read authenticated responses.
- **Allowing `null`.** In the vulnerable build `Origin: null` gets `Access-Control-Allow-Origin: null` plus `Access-Control-Allow-Credentials: true`. Sandboxed frames and some redirects can send `null`, so it identifies nobody.
- **A prefix or regex that is too loose.** The test in the demo compares two matchers on three origins:

```
https://app.example.test                 bad=true  good=true
https://app.example.test.evil.test       bad=true  good=false
null                                     bad=false good=false
```

`bad` is `strings.HasPrefix`, and it accepts the lookalike `app.example.test.evil.test` that an attacker can register. `good` is an exact lookup in a map. If you must use a regex, anchor it with `^...$`; better, do not.

- **`*` together with cookies.** MDN says that for a credentialed request the server must not use the `*` wildcard in `Access-Control-Allow-Origin`; it must name the origin, and the browser blocks the response otherwise.

## CSRF defences, with results

Now the fixed build. The login cookie gets `SameSite=Lax` (this is the header; I did not test the browser side):

```
Set-Cookie: sid=s-alice; Path=/; HttpOnly; SameSite=Lax
```

`Lax` asks the browser to leave the cookie off most cross-site requests, which already stops the hidden form above. It is one layer, and the server should not depend on it alone. So `/transfer` has two more. The demo script first fetches a CSRF token with `GET /csrf` and checks the balance (100). Then it sends five requests with curl, each with Alice's cookie:

```
Origin: https://evil.test                              -> 403 cross-site request refused
Origin: https://evil.test + valid token                -> 403 cross-site request refused
Sec-Fetch-Site: cross-site                             -> 403 cross-site request refused
Sec-Fetch-Site: same-origin, no token                  -> 403 bad csrf token
no Origin, no Sec-Fetch-Site, valid token              -> 403 cross-site request refused
```

The balance was still 100 after all five. Finally:

```
Sec-Fetch-Site: same-origin + valid token              -> 200 {"balance":70}
```

The layers, one by one:

1. **Origin and `Sec-Fetch-Site` check.** Browsers add these headers themselves and page scripts cannot override them (they are forbidden header names in the Fetch spec). The server accepts the request only if `Sec-Fetch-Site` says `same-origin` or `none`, or, when that header is absent, if the `Origin` host equals the `Host` of the request. Requests with neither header are refused. That is why the last of the five fails even with a valid token, and it also means non-browser clients are refused, so a real API needs another way to authenticate them.
2. **Synchroniser token.** `GET /csrf` returns an HMAC of the session id (a value the attacker's page cannot read, because of the same-origin policy), and `/transfer` requires it in the `csrf` form field. That is why "same-origin, no token" fails with `bad csrf token`.
3. **Double-submit cookie**, for the JSON endpoint `/api/settings`. The server sets a `csrf` cookie, and the request must repeat its value in the `X-CSRF-Token` header. A foreign page can make the browser send the cookie, but cannot read it to copy it into the header. With the cookie but no header, or a wrong header, I got `403 bad csrf token`; with a matching header, `200 {"saved":{"a":1}}`. It is weaker when subdomains are untrusted, because a sibling subdomain can set cookies for the whole site.

## Security headers

The fixed build adds six headers to every response. I checked them with `curl -i` on a normal route and on a 404:

| Header | Purpose |
|---|---|
| `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` | load only same-origin resources; forbid framing the page |
| `Strict-Transport-Security: max-age=31536000; includeSubDomains` | {{< term "hsts" "HSTS" >}}: use HTTPS from now on, for a year |
| `X-Content-Type-Options: nosniff` | do not guess a file's type, trust `Content-Type` |
| `Referrer-Policy: strict-origin-when-cross-origin` | send less of the URL to other sites |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | switch off these browser features for the page |
| `Cross-Origin-Opener-Policy: same-origin` | keep the window isolated from cross-origin windows that opened it |

According to RFC 6797, a browser must ignore HSTS when it receives it over plain HTTP, so on this localhost demo the header is only shown, and it matters on HTTPS (the next post).

A test keeps the headers from disappearing. It sends a request to every route plus an unknown path (the 404) and asserts that all six headers are present. `go test` passes. The middleware wraps the whole mux, so error responses are covered too. The test output for the matchers above came from the same `go test -v` run.

## Layers, not a single fix

- CORS controls who may read, not who may send. Protect state-changing requests with tokens or origin checks.
- Allow-list exact origins, send `Vary: Origin`, never reflect the request's origin blindly, and never allow `null`.
- Do not rely on `SameSite` alone; it is one layer, and browsers differ in their defaults.
- Do not change state on `GET`. `Lax` still lets a cross-site link navigation carry the cookie on a `GET`.
- Headers are defence in depth. They do not fix XSS or missing authorization.

## Exercise

Make `/transfer` accept a JSON body with the token in `X-CSRF-Token`, and add a test where a forged `Origin` together with a valid token still gets 403.

## What's next

"TLS and x509 certificates in practice" hardens the connection underneath everything here, and it is where HSTS finally takes effect.
