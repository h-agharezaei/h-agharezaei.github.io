+++
date = '2027-02-21T10:00:00+03:30'
draft = false
title = 'The OWASP Top 10 in real code'
description = 'The OWASP Top 10 in real code: the 2025 categories mapped to Go, with local demos of IDOR, exposed pprof, log injection and SSRF, each with a fix.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "owasp", "appsec", "go", "idor", "ssrf"]
cover = { image = "/images/covers/sec-owasp-top10-in-code.png", alt = "The OWASP Top 10 in real code", hiddenInSingle = true }
+++

Imagine an orders endpoint that finds an order by its ID and returns it. Alice logs in, opens her order number 1, and then, out of curiosity, changes the URL to order number 2. She gets Bob's order. Nothing crashed and no one "hacked" anything; the handler simply never asked whose order it was.

Bugs like this have names, and the most widely used list of names is the {{< term "owasp-top-10" "OWASP Top 10" >}}. OWASP is a non-profit that publishes security guidance, and the Top 10 is its ranked list of the most common kinds of web application weakness. The previous post, [Threat modeling with STRIDE](/posts/sec-threat-modeling-stride/), gave us six kinds of threat to look for. The Top 10 is the other half of the vocabulary: the names you will hear in code reviews, audit reports and job interviews. In this post I put those names next to real code. Each demo is the `orders` idea from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), reduced to a tiny program, first broken and then fixed.

I read the OWASP Top 10 page on 2026-10-27 and it redirected to **OWASP Top 10:2025**; I checked it again while rewriting this post (on its 2025 page, now hosted at top10.owasp.org), and the category names below are copied from there.

> Defensive only. Every demo is my own standard-library Go program on `127.0.0.1`. I re-ran them with Go 1.27 (the first run used Go 1.26). To avoid port clashes I ran them on random free ports; the commands below keep the original `82xx` ports for readability. The "user" is an `X-User` header that stands in for a verified login token, so the demos can stay small.

## The ten categories

Here is the whole list, with the demo that covers each one (if there is one):

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

Not every category fits a ten-line demo. A06, for example, is exactly what the previous post is about, and A07 gets its own posts later in the series. I only show the ones that can be seen in a small program.

One more thing: SSRF (demo 4) was its own category in the 2021 list. When I fetched the 2025 page, its category list did not mention SSRF, and I did not find where that edition files it. So I treat it here as a standalone weakness.

## Demo 1: broken access control

This demo is the opening story. The handler looks an order up by ID and returns it. The program holds two orders, number 1 owned by alice and number 2 owned by bob. This mistake is called an {{< term "idor" "IDOR" >}}, an insecure direct object reference: the endpoint hands out an object by its ID without checking that the caller may see it. Alice asks for order 2:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8201/orders/2
{"id":"2","owner":"bob","sku":"laptop"}
```

The answer shows `"owner":"bob"`. Alice read Bob's order.

The fix is one comparison: `o.Owner` against the caller. And when the check fails, the handler answers 404, the same as for an order that does not exist. That is deliberate: a "403 forbidden" would tell Alice that order 2 exists, so she could still probe which IDs are real. With 404 she learns nothing:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/2
{"error":"not found"}
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/1
{"id":"1","owner":"alice","sku":"book"}
```

Order 2 is now "not found" for Alice, and her own order 1 still works.

## Demo 2: security misconfiguration

Sometimes nothing in your code is wrong; a feature is simply left switched on where it should not be. Go has a good example. Importing `net/http/pprof` registers profiling handlers (under `/debug/pprof/`) on Go's default mux, the global request router. In a public service, mounting that mux on the public router exposes them to everyone. I ask for one of the pages:

```
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8211/debug/pprof/cmdline
200
```

`-o /dev/null` throws the body away and `-w '%{http_code}\n'` prints only the status code. 200 means the profiling endpoint answers on the public port. These pages show how the process is running, and the heavier ones can slow the service down, so they are not for the public.

The fix keeps {{< term "pprof" "pprof" >}} on the default mux but serves that mux from a second listener bound to `127.0.0.1` only. The public port then answers 404 for that path, and the admin port answers 200 (I checked both on the fixed program). Profiling itself is covered in [Profiling Go with pprof](/posts/go-profiling-pprof/). Binding to loopback is the minimum; a real deployment also needs network rules around the admin port.

## Demo 3: logging failures

A security log is only useful if it can be trusted. A username that contains a newline can forge a log line when the program builds log lines by hand. This program prints the same "login failed" event twice, once with `Printf`-style formatting and once with `log/slog`. The username is `bob`, then a newline, then a fake "login ok" entry for `admin`:

```
level=INFO msg="login failed" user=bob
time=2027-02-21 level=INFO msg="login ok" user=admin
```

That is two lines, and the second one never happened. This is {{< term "log-injection" "log injection" >}}: anyone reading or searching the log sees an `admin` login that did not occur. With `log/slog` the value is quoted and the newline escaped, so one event stays one line:

```
level=INFO msg="login failed" user="bob\ntime=2027-02-21 level=INFO msg=\"login ok\" user=admin"
```

The whole attempt now sits inside the quoted `user=` value, easy to see and impossible to mistake for a separate event. More on logging in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). This demo covers only the "recording" half of A09; alerting (someone being notified) is not shown.

## Demo 4: SSRF

The next one concerns a server that makes requests for the user. A `/fetch?url=` handler downloads whatever address it is given, for example to build a preview of a link. I started a fake "internal" service on a loopback port, standing in for something that should not be reachable from outside, such as an admin page or a metadata service. Then I asked the public handler to fetch it:

```
$ curl -s '127.0.0.1:8221/fetch?url=http://127.0.0.1:8223/secret'
internal-only: db-password-demo
```

That is {{< term "ssrf" "SSRF" >}}, server-side request forgery: the server fetched something the caller could not reach directly, and returned it. (`db-password-demo` is text I made up.)

The fix allows only `https` URLs and only hosts from an {{< term "allow-list" "allow-list" >}}, a list of the only values accepted. The same request now fails:

```
$ curl -s '127.0.0.1:8222/fetch?url=http://127.0.0.1:8223/secret'
{"error":"url not allowed"}
```

My allow-list is a single example host. I did not test redirects or DNS tricks, which a real fix must handle; the series comes back to this in [SSRF and unsafe deserialization](/posts/sec-ssrf-deserialization/).

## Demo 5: cryptographic failures

The last demo is a password table. It computes the SHA-256 of the same password for two different users:

```
alice f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
bob f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
```

(The password, `hunter2`, is a throwaway example.) The two hashes are identical. Anyone who reads this table can see that alice and bob chose the same password, and a fast hash like SHA-256 is cheap to guess against: a program can try a huge number of guesses per second. The proper approach is the topic of the next-but-one post in this series, [Storing passwords safely: argon2 and bcrypt](/posts/sec-password-hashing/).

## Supply chain: what I could not run

For A03 I planned to run `govulncheck` on a module that pins an old `golang.org/x/text`. The vulnerability database request (`vuln.go.dev`) returned `403 Forbidden` here, both in the first run and when I retried while rewriting this post, so I have no real finding and show none. Run `govulncheck ./...` in your own CI.

## Rules of thumb from the demos

- **Check access on the server, for every object.** Hiding a link in the UI is not access control; the endpoint itself must ask "is this yours?".
- **Put debug features on a separate, non-public listener.** And do not rely on that alone.
- **Never build log lines by string concatenation.** Use a structured logger that escapes values.
- **Allow-lists beat block-lists for outgoing URLs.** You cannot list every bad address; you can list the few good ones.
- **The Top 10 is an awareness list.** Passing it does not mean "secure".

## Exercise

Add `DELETE /orders/{id}` to demo 1. Does your ownership check cover it? Write a test that proves Alice gets 404.

## What's next

The next post is "Injection and XSS". It takes the Injection category from the table (A05) and goes deep on it: SQL, shell, filesystem and browser.
