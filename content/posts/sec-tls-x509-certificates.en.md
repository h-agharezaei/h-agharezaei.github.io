+++
date = '2027-04-24T10:00:00+03:30'
draft = false
title = 'TLS and x509 certificates in practice'
description = 'TLS and x509 certificates in Go on loopback: verify errors, chains, rotation with GetCertificate, mutual TLS, expiry checks and pinning.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "tls", "x509", "certificates", "mtls", "go"]
cover = { image = "/images/covers/sec-tls-x509-certificates.png", alt = "TLS and x509 certificates in practice", hiddenInSingle = true }
+++

The previous post, [CSRF, CORS and security headers](/posts/sec-csrf-cors-headers/), hardened what the browser does. Here we harden the pipe itself. [TLS and certificates with openssl](/posts/net-tls-openssl/) covered the `openssl` command line; this post is the Go and operations side: what is inside an {{< term "x509-certificate" "x509 certificate" >}}, why verification fails, and how to rotate and monitor certificates. The server is the kind of API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Defensive only. Everything ran on `127.0.0.1` in one Go 1.26 program using only the standard library. I created my own throwaway {{< term "certificate-authority" "CA" >}} in code (ECDSA P-256); there is no public CA here. Private keys never touched disk. ACME, OCSP and CT are explained only, not run. Times in the output are my local clock.

## What is inside a certificate

`x509.CreateCertificate` signs a template; parsing it gives these fields (trimmed):

```
subject     CN=orders.local,O=Demo
issuer      CN=Demo Root CA,O=Demo
serial      ...3c4d
dns SANs    [orders.local localhost]
ip SANs     [127.0.0.1]
IsCA        false  basicConstraintsValid true
KeyUsage    DigitalSignature=true, CertSign=false
ExtKeyUsage [serverAuth]
```

The CA has `IsCA true` and `CertSign=true`. Clients match names against the {{< term "subject-alt-name" "SAN" >}} list, so put every DNS name and IP there. I print only the last bytes of the serial.

## The errors, for real

`Verify` with a root pool, a name and the usage `serverAuth`:

```
unknown authority  x509: certificate signed by unknown authority
hostname mismatch  x509: certificate is valid for orders.local, localhost, not payments.local
expired            x509: certificate has expired or is not yet valid: current time 2026-10-27T10:27:14+03:30 is after 2026-10-26T06:57:14Z
not yet valid      x509: certificate has expired or is not yet valid: current time 2026-10-27T10:27:14+03:30 is before 2026-10-28T06:57:14Z
wrong ExtKeyUsage  x509: certificate specifies an incompatible key usage
no intermediate    x509: certificate signed by unknown authority
with intermediate  ok
```

The wrong-usage case was a certificate meant for `clientAuth`. Note that "no intermediate" prints the same text as an unknown CA, which makes it confusing in production.

## Chains over a real connection

A {{< term "certificate-chain" "certificate chain" >}} is leaf, intermediate, root. I issued the leaf from an intermediate and served it two ways. With only the leaf, the Go client says:

```
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

With `tls.Certificate{Certificate: [][]byte{leaf, intermediate}}` the request returned `hello` and the client saw a chain of length 2. The server must send the intermediates. In my test the Go client did not fetch a missing one by itself.

## Versions and cipher suites

With `MinVersion: tls.VersionTLS12` on the server, `resp.TLS` shows the result:

```
client max TLS 1.2 -> TLS 1.2, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
client max TLS 1.3 -> TLS 1.3, TLS_AES_128_GCM_SHA256
client max TLS 1.1 -> tls: no supported versions satisfy MinVersion and MaxVersion
```

Set `MinVersion` explicitly and leave the cipher list to Go.

## Rotation without a restart

`GetCertificate` runs on every handshake, so swapping a pointer rotates the certificate. I held an `atomic.Pointer[tls.Certificate]`, served A, replaced it with B on the same listener:

```
before swap, client sees serial ...aaaa
after swap,  client sees serial ...bbbb (same listener, same address)
```

In production you reload from disk on a signal or a timer. Existing connections keep their old certificate.

## Mutual TLS

With `ClientAuth: tls.RequireAndVerifyClientCert` and `ClientCAs`, this is {{< term "mutual-tls" "mutual TLS" >}}:

```
no client cert     -> remote error: tls: certificate required
cert from other CA -> remote error: tls: certificate required
valid client cert  -> hello orders-client
```

The second line surprised me: Go's client only sends a certificate whose issuer the server listed, so the rogue one was never sent. I did not force it to send it.

## A monitoring check

`certcheck` (a small program of mine) connects, verifies, and computes days left. The demo server's leaf lived 10 days plus an hour:

```
$ certcheck 127.0.0.1:PORT 14 ca.pem   -> WARN orders.local expires in 10 days (limit 14)   exit=1
$ certcheck 127.0.0.1:PORT 7 ca.pem    -> OK orders.local expires in 10 days                exit=0
$ certcheck 127.0.0.1:PORT 7 /dev/null -> UNKNOWN cannot load CA file                       exit=2
```

Exit codes 0, 1, 2 work for cron or any monitor. Alert at 14 days or more, because renewals fail.

## Pinning and `InsecureSkipVerify`

{{< term "certificate-pinning" "Pinning" >}} compares the SHA-256 of the public key (SPKI) in `VerifyConnection`. Pinned to key A: server A passed, server B failed with `pin mismatch: got b1acadcaca83edc9...`. Pins make rotation harder, so most services should not pin.

The anti-pattern:

```
RootCAs, wrong name   -> x509: certificate is valid for orders.local, localhost, not payments.local
InsecureSkipVerify    -> hello <nil>
RootCAs, right name   -> hello <nil>
```

`InsecureSkipVerify` hid the mismatch completely. The fix is `RootCAs` plus `ServerName`.

## ACME and revocation (not run)

{{< term "acme" "ACME" >}} automates issuance and renewal, which is why short lifetimes work. {{< term "ocsp" "OCSP" >}} asks a CA if a certificate was revoked; Certificate Transparency logs public issuance. I ran none of them, and as far as I know the Go client does not check revocation by itself.

## A few things to watch

- Send the full chain except the root.
- Verify name and usage, never skip verification.
- Monitor expiry; do not rely on memory.
- Set `MinVersion` explicitly.
- Keep keys out of repositories.

## Exercise

Extend `certcheck` to take the host name from its argument instead of a constant, and add a flag that prints the SANs. Then break it with a wrong CA file and confirm exit code 2.

## What's next

The next post is Managing secrets and keys.
