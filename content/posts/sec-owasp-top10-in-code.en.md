+++
date = '2027-02-21T10:00:00+03:30'
draft = false
title = 'The OWASP Top 10 in real code'
description = 'The OWASP Top 10 in real code: the 2025 categories mapped to Go, with local demos of IDOR, exposed pprof, log injection and SSRF, each with a fix.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "owasp", "appsec", "go", "idor", "ssrf"]
cover = { image = "/images/covers/sec-owasp-top10-in-code.png", alt = "The OWASP Top 10 in real code", hiddenInSingle = true }
+++

[Threat modeling with STRIDE](/posts/sec-threat-modeling-stride/) gave us a ranked list of threats. The {{< term "owasp-top-10" "OWASP Top 10" >}} is the usual vocabulary for them, so here I map it to code: the `orders` idea from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), reduced to tiny programs.

I read https://owasp.org/Top10/ on 2026-10-27; it redirected to **OWASP Top 10:2025**, and the names below are copied from that page.

> Defensive only. Every demo is my own stdlib Go program on `127.0.0.1` (Go 1.26). The "user" is an `X-User` header standing in for a verified token.

## The ten categories

| # | Category | In one sentence |
|---|---|---|
| A01 | Broken Access Control | a user reaches data or actions they should not (demo 1) |
| A02 | Security Misconfiguration | unsafe defaults or exposed debug features (demo 2) |
| A03 | Software Supply Chain Failures | vulnerable or tampered dependencies and build steps |
| A04 | Cryptographic Failures | weak or missing protection of data and secrets (demo 5) |
| A05 | Injection | untrusted input interpreted as code or commands (next post) |
| A06 | Insecure Design | the flaw is in the design, not the code; see threat modeling |
| A07 | Authentication Failures | weak login, sessions or credential handling |
| A08 | Software or Data Integrity Failures | trusting code or data without verifying it |
| A09 | Security Logging and Alerting Failures | attacks are not recorded or noticed (demo 3) |
| A10 | Mishandling of Exceptional Conditions | errors that fail open or leak details |

SSRF (demo 4) was its own category in the 2021 list; I am not claiming where the 2025 edition files it, so I treat it as a standalone weakness.

## Demo 1: broken access control

The naive handler looks an order up by ID and returns it. This is an {{< term "idor" "IDOR" >}}:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8201/orders/2
{"id":"2","owner":"bob","sku":"laptop"}
```

Alice read Bob's order. The fix compares `o.Owner` with the caller and answers 404 for both "missing" and "not yours", so IDs cannot be probed:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/2
{"error":"not found"}
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/1
{"id":"1","owner":"alice","sku":"book"}
```

## Demo 2: security misconfiguration

Importing `net/http/pprof` registers handlers on the default mux. Mounting that mux on the public one exposes them:

```
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8211/debug/pprof/cmdline
200
```

The fix serves {{< term "pprof" "pprof" >}} from a second listener on `127.0.0.1` only (public port: 404, admin port: 200). Profiling itself is in [Profiling Go with pprof](/posts/go-profiling-pprof/). Binding to loopback is a minimum; a real deployment also needs network rules.

## Demo 3: logging failures

A username with a newline can forge a log line. With `Printf`-style logging:

```
level=INFO msg="login failed" user=bob
time=2027-02-21 level=INFO msg="login ok" user=admin
```

That is {{< term "log-injection" "log injection" >}}: a fake "login ok" for admin. With `log/slog` the value is quoted and escaped, one event stays one line:

```
level=INFO msg="login failed" user="bob\ntime=2027-02-21 level=INFO msg=\"login ok\" user=admin"
```

See [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). This covers only the "recording" half of A09; alerting is not shown.

## Demo 4: SSRF

A `/fetch?url=` handler downloads whatever it is given. I started a fake internal service on loopback:

```
$ curl -s '127.0.0.1:8221/fetch?url=http://127.0.0.1:8223/secret'
internal-only: db-password-demo
```

That is {{< term "ssrf" "SSRF" >}}: the server fetched something the caller could not reach. The fix allows only `https` and a host allow-list:

```
$ curl -s '127.0.0.1:8222/fetch?url=http://127.0.0.1:8223/secret'
{"error":"url not allowed"}
```

My allow-list is a single example host; I did not test redirects or DNS tricks, which a real fix must handle.

## Demo 5: cryptographic failures

Unsalted SHA-256 of the same password for two users:

```
alice f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
bob f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
```

Equal hashes reveal equal passwords, and a fast hash is cheap to guess against. The proper approach is the topic of “Storing passwords safely: argon2 and bcrypt”.

## Supply chain: what I could not run

I planned to run `govulncheck` on a module pinning an old `golang.org/x/text`. The vulnerability database request (`vuln.go.dev`) returned `403 Forbidden` here, so I have no real finding and show none. Run `govulncheck ./...` in your own CI.

## A few things to watch

- Check access on the server for every object, not just in the UI.
- Debug features belong on a separate, non-public listener.
- Never build log lines by string concatenation.
- Allow-lists beat block-lists for outgoing URLs.
- The Top 10 is an awareness list; passing it does not mean secure.

## Exercise

Add `DELETE /orders/{id}` to demo 1. Does your ownership check cover it? Write a test that proves Alice gets 404.

## What's next

The next post is “Injection and XSS”.
