+++
date = '2027-04-24T10:00:00+03:30'
draft = false
title = 'TLS and x509 certificates in practice'
description = 'TLS and x509 certificates in Go on loopback: verify errors, chains, rotation with GetCertificate, mutual TLS, expiry checks and pinning.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "tls", "x509", "certificates", "mtls", "go"]
cover = { image = "/images/covers/sec-tls-x509-certificates.png", alt = "TLS and x509 certificates in practice", hiddenInSingle = true }
+++

You deploy a service, point a Go client at it, and get this:

```
x509: certificate signed by unknown authority
```

The obvious reading is "the client does not trust the server's certificate authority". Sometimes that is true. But the same message also appears when the certificate authority is perfectly trusted and the server simply forgot to send one file. When two different problems print the same error, you need to know what the client actually checks. That is what this post is about.

[CSRF, CORS and security headers](/posts/sec-csrf-cors-headers/) hardened what the browser does with a page. Here we harden the pipe underneath. [TLS and certificates with openssl](/posts/net-tls-openssl/) covered the `openssl` command line, with the same checks seen from outside; this post is the Go and operations side: what is inside an {{< term "x509-certificate" "x509 certificate" >}}, why verification fails, how to rotate a certificate without a restart, and how to notice before one expires. The server is the kind of API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Defensive only. Everything ran on `127.0.0.1` in one Go program using only the standard library (Go 1.27.3 on macOS arm64; the demo's `go.mod` says 1.26). I created my own throwaway {{< term "certificate-authority" "certificate authority" >}} (CA) in code, with ECDSA P-256 keys; there is no public CA here. Private keys never touched disk (the one server that writes a file writes only its CA certificate). ACME, OCSP and Certificate Transparency are explained only, not run. Times in the output are my local clock, and the random parts (port numbers, pin hashes) change on every run.

## What a client checks

A certificate is a signed statement: "this public key belongs to this name, for this period". The signer is the **issuer**. When a client connects, the server sends its certificate, the **leaf**, and proves it holds the matching private key. Then the client asks four questions:

1. Is the leaf signed by someone I trust? The signature must lead, through a **chain** (leaf, then intermediate CAs, then a **root**), to a root certificate in the client's trusted set.
2. Does the name I connected to appear in the certificate? Names live in the {{< term "subject-alt-name" "SubjectAltName" >}} (SAN) list.
3. Is today inside the validity period?
4. Is the certificate allowed to be used this way? The extended key usage (`serverAuth`, `clientAuth`) says what it is for.

Go's `Verify` asks exactly these. The rest of the post breaks each of them on purpose.

## What is inside a certificate

The demo builds the CA and a leaf with `x509.CreateCertificate`, and then parses the leaf and prints its fields:

```
subject     CN=orders.local,O=Demo
issuer      CN=Demo Root CA,O=Demo
serial      ...3c4d
dns SANs    [orders.local localhost]
ip SANs     [127.0.0.1]
valid for   25h0m0s
IsCA        false  basicConstraintsValid true
KeyUsage    1 (DigitalSignature=true, CertSign=false)
ExtKeyUsage [serverAuth]
sig alg     ECDSA-SHA256
```

The `subject` is who the certificate is for; the `issuer` is the CA that signed it. The demo prints only the last digits of the serial. The two SAN lines are what clients match names against, so put every DNS name and IP address there. `valid for` is one hour in the past to 24 hours ahead. `IsCA false` and `CertSign=false` say this certificate cannot sign other certificates, and `ExtKeyUsage [serverAuth]` says it is meant for servers. The CA's certificate, printed right after, has `IsCA true` and `CertSign=true`.

## The errors, for real

Now the same `Verify` call with a root pool, a name and the usage `serverAuth`, on a good leaf and on six broken setups:

```
good               ok
unknown authority  x509: certificate signed by unknown authority
hostname mismatch  x509: certificate is valid for orders.local, localhost, not payments.local
expired            x509: certificate has expired or is not yet valid: current time 2026-11-04T21:05:27+03:30 is after 2026-11-03T17:35:27Z
not yet valid      x509: certificate has expired or is not yet valid: current time 2026-11-04T21:05:27+03:30 is before 2026-11-05T17:35:27Z
wrong ExtKeyUsage  x509: certificate specifies an incompatible key usage
no intermediate    x509: certificate signed by unknown authority
with intermediate  ok
```

Line by line:

- **unknown authority**: I verify against a root pool that holds a different CA. The leaf does not chain to anything the client trusts.
- **hostname mismatch**: the leaf is fine, but I asked for `payments.local`, and the error even lists the names it is valid for. This is the most helpful message of the set.
- **expired** and **not yet valid**: the same error text, with the current time and the boundary. A clock that is wrong gives you the second one on a perfectly good certificate.
- **wrong ExtKeyUsage**: this leaf was issued for `clientAuth` and I asked for `serverAuth`.
- **no intermediate** and **with intermediate**: here the leaf is signed by an intermediate CA, which is signed by the root. If the client has only the root, it cannot connect the two and says "unknown authority", the same text as the first line. Give it the intermediate and the chain closes.

## Chains over a real connection

The "no intermediate" line is the confusing one in production, so let me show it on a real connection. The leaf is issued from the intermediate. First a server that sends only the leaf. The Go client says:

```
leaf only      -> Get "https://127.0.0.1:55975/": tls: failed to verify certificate: x509: certificate signed by unknown authority
```

Then a server that sends the leaf and the intermediate, with `tls.Certificate{Certificate: [][]byte{leaf, intermediate}}` (that is what `l2.TLS(inter)` builds in the demo):

```
leaf+inter     -> hello <nil> chain length seen by client: 2
```

The request returns `hello` and the client sees a chain of length 2. So the server must send the intermediates (not the root: the client already has it). In my test the Go client did not fetch a missing intermediate by itself. A browser may behave differently, which is one reason a broken chain can look fine in one place and fail in another.

## Versions and cipher suites

The next check is the TLS version. The server sets `MinVersion: tls.VersionTLS12`, and I let the client's maximum version vary. `resp.TLS` shows what was negotiated:

```
client max TLS 1.2 -> TLS 1.2, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256, body="hello"
client max TLS 1.3 -> TLS 1.3, TLS_AES_128_GCM_SHA256, body="hello"
client max TLS 1.1 -> Get "https://127.0.0.1:55971/": tls: no supported versions satisfy MinVersion and MaxVersion
```

The first two lines negotiate what the client allows. The third line is worth reading carefully. It is the client that refuses: a Go client with `MaxVersion` 1.1 is in conflict with its own default minimum (TLS 1.2), so no connection is even attempted. This does not show the server rejecting an old client. The advice is the same: set `MinVersion` explicitly and leave the cipher list to Go.

## Rotation without a restart

Certificates expire, so you will swap them. `GetCertificate` is called on every handshake, so changing what it returns rotates the certificate on a live listener. The demo holds an `atomic.Pointer[tls.Certificate]`, serves certificate A, then replaces it with B:

```
before swap, client sees serial ...aaaa
after swap,  client sees serial ...bbbb (same listener, same address)
```

The client sees the new serial on the next connection, with no restart. In production you would reload from disk on a signal or on a timer. Connections that are already open keep the certificate they started with.

## Mutual TLS

In ordinary TLS only the server shows a certificate. With `ClientAuth: tls.RequireAndVerifyClientCert` and a `ClientCAs` pool, the server also demands one from the client. That is {{< term "mutual-tls" "mutual TLS" >}}, common between internal services:

```
no client cert    -> Get "https://127.0.0.1:55982/": remote error: tls: certificate required
cert from other CA-> Get "https://127.0.0.1:55982/": remote error: tls: certificate required
valid client cert -> hello orders-client <nil>
```

The second line surprised me: it gives the same error as sending nothing. Go's client only offers a certificate whose issuer the server listed as acceptable, so the rogue certificate was never sent. In the original run I did not force it to be sent. This time I did, in a scratch copy, by giving the client a `GetClientCertificate` callback that returns the rogue certificate anyway. Then the server answered:

```
forced rogue -> Get "https://127.0.0.1:56067/": remote error: tls: unknown certificate authority
```

So a certificate from the wrong CA is rejected either way, with a different message depending on whether the client sent it.

## A monitoring check

Expiry is the most boring and the most common cause of TLS outages, so check it from outside. `certcheck` is a small program of mine: it connects, verifies against a CA file, and computes the days left on the leaf. The demo server's leaf lives 10 days plus an hour. (The host name inside `certcheck` is a constant, `orders.local`, which the exercise below removes.)

```
$ certcheck 127.0.0.1:PORT 14 ca.pem   -> WARN orders.local expires in 10 days (limit 14)   exit=1
$ certcheck 127.0.0.1:PORT 7 ca.pem    -> OK orders.local expires in 10 days                exit=0
$ certcheck 127.0.0.1:PORT 7 /dev/null -> UNKNOWN cannot load CA file                       exit=2
```

`14` and `7` are the minimum days left. With a limit of 14, the 10-day certificate warns; with 7 it is fine; and with a broken CA file the tool refuses to guess and says UNKNOWN. The exit codes 0, 1 and 2 work for cron or any monitoring system. Warn early, 14 days or more, because automated renewals fail too and you want time to notice.

## Pinning and `InsecureSkipVerify`

{{< term "certificate-pinning" "Pinning" >}} means the client accepts only a server whose public key has a hash it already knows. The demo compares the SHA-256 of the public key (SPKI) inside `VerifyConnection`. Pinned to key A, server A passes and server B fails:

```
pin (sha256 of SPKI, first 16 hex): 20fd40a79e4fe868
server key ...aaaa: err=<nil>
server key ...bbbb: err=Get "https://127.0.0.1:55988/": pin mismatch: got ca33a5ac52cd79b2...
```

Pins make rotation harder, since the next certificate must keep the pinned key or ship with a new pin first, so most services should not pin.

Now the anti-pattern. Developers often silence a verification error with `InsecureSkipVerify`:

```
RootCAs, wrong name   -> Get "https://127.0.0.1:55990/": tls: failed to verify certificate: x509: certificate is valid for orders.local, localhost, not payments.local
InsecureSkipVerify    -> hello <nil>
RootCAs, right name   -> hello <nil>
```

With the right setup, asking for the wrong name fails. With `InsecureSkipVerify` the same wrong name just works, so the mismatch is completely hidden, and so would be a real attacker's certificate. The correct fix is `RootCAs` plus the right `ServerName`.

## ACME and revocation (not run)

Three things are only explained here. {{< term "acme" "ACME" >}} is the protocol that automates issuing and renewing certificates; it is the reason very short lifetimes are practical. {{< term "ocsp" "OCSP" >}} lets a client ask a CA whether a certificate was revoked. Certificate Transparency is a set of public logs of issued certificates. I ran none of them. As far as I know, Go's `crypto/x509` verification does not check revocation by itself, so do not assume a revoked certificate fails there.

## Operational habits

- Send the full chain except the root. A missing intermediate looks like an untrusted CA.
- Verify name and usage, and never skip verification to make an error go away.
- Monitor expiry from outside; do not rely on memory.
- Set `MinVersion` explicitly.
- Keep private keys out of repositories.

## Exercise

Extend `certcheck` to take the host name from its argument instead of a constant, and add a flag that prints the SANs. Then break it with a wrong CA file and confirm exit code 2.

## What's next

"Managing secrets and keys" picks up the last habit above: how keys and other secrets leak anyway, and how to load them safely.
