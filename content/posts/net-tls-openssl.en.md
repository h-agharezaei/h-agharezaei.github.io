+++
date = '2027-03-01T10:00:00+03:30'
draft = false
title = 'TLS and certificates with openssl'
description = 'TLS and certificates with openssl on loopback: build a CA, sign a certificate with a SAN, read verification errors, TLS 1.2 vs 1.3, ALPN and mutual TLS.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tls", "openssl", "certificates", "mtls", "security"]
cover = { image = "/images/covers/net-tls-openssl.png", alt = "TLS and certificates with openssl", hiddenInSingle = true }
+++

In the previous post, [HTTP/1.1 by hand](/posts/net-http1-by-hand/), we typed HTTP requests over a plain socket, and anyone on the path could read them. {{< term "tls" "TLS" >}} fixes that: it encrypts the connection and proves who the server is. Most TLS pain is not cryptography, it is certificates and error messages. So we build the whole chain ourselves with `openssl`, break it on purpose, and read each error. It sits on top of [the TCP/IP model](/posts/net-tcp-ip-model/) and [TCP connections](/posts/net-tcp-handshake-states/).

> Everything ran on `127.0.0.1` with throwaway files in a temp directory (`<tmp>`), so there is nothing personal in the output. I used Homebrew's `/opt/homebrew/bin/openssl` (OpenSSL 3.6.4); macOS's `/usr/bin/openssl` is LibreSSL 3.3.6 and has different options. The port is shown as `PORT`. No packet capture was possible (no root).

## A CA and a server certificate

A {{< term "certificate-authority" "certificate authority" >}} (CA) is just a key plus a self-signed certificate. We make one, then a server key and a request, and sign it:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 30 -subj "/CN=Demo Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" -out ca.pem
openssl genpkey ... -out server.key ; openssl req -new -key server.key -subj "/CN=localhost" -out server.csr
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 7 -sha256 \
  -extfile ext.cnf -out server.pem
```

`ext.cnf` holds the important part, the {{< term "subject-alt-name" "SubjectAltName" >}}:

```
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
```

Why not just the Common Name? Clients match the host name against the SAN list. I made a second certificate with no SAN (`nosan.pem`) and tried it. OpenSSL's `-verify_hostname localhost` still printed `Verification: OK` because it falls back to the CN. A Go client (`crypto/tls`) refused it:

```
error: tls: failed to verify certificate: x509: certificate relies on legacy Common Name field, use SANs instead
```

So always set the SAN. Trimmed from `openssl x509 -in server.pem -noout -text` ({{< term "x509-certificate" "X.509" >}}):

```
Issuer: CN=Demo Root CA
Not Before: Oct 27 05:49:49 2026 GMT
Not After : Nov  3 05:49:49 2026 GMT
Subject: CN=localhost
Public Key Algorithm: id-ecPublicKey
X509v3 Extended Key Usage: TLS Web Server Authentication
X509v3 Subject Alternative Name: DNS:localhost, IP Address:127.0.0.1
```

`openssl verify -CAfile ca.pem server.pem` prints `server.pem: OK`.

## Connect and verify

I started a server with `openssl s_server -accept PORT -cert server.pem -key server.key -www`, then:

```
$ openssl s_client -connect 127.0.0.1:PORT -CAfile ca.pem -servername localhost -verify_hostname localhost </dev/null
depth=1 CN=Demo Root CA
depth=0 CN=localhost
Peer signature type: ecdsa_secp256r1_sha256
Verification: OK
Verified peername: localhost
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
Verify return code: 0 (ok)
```

`-servername` sends {{< term "sni" "SNI" >}}, the name the client wants, inside the handshake. The cipher line is the negotiated result. Forcing `-tls1_2` gives `ECDHE-ECDSA-AES256-GCM-SHA384`.

I also tried `curl --cacert`, but on this Mac both the system curl and Homebrew's use Apple's SecureTransport backend and printed `unable to get local issuer certificate (20), continuing anyway` and fetched the page. I do not trust it for this demo, so I show only `openssl` and Go results.

## The failures, for real

```
# 1. client does not know our CA
Verification error: unable to verify the first certificate     (code 21; also num=20 unable to get local issuer certificate)
# 2. name not in the SAN (-verify_hostname example.org)
verify error:num=62:hostname mismatch
# 3. expired certificate
verify error:num=10:certificate has expired
```

1. Without `-CAfile` no trusted CA signed the certificate. Fix: trust the right CA, never turn verification off.
2. The certificate is valid, but not for that name. The check protects against a valid certificate for another site.
3. I made the third one with `openssl x509 -req ... -not_before 20260101000000Z -not_after 20260102000000Z` (my OpenSSL 3.6 accepts these options). `openssl verify` reports the same error 10.

## TLS 1.2, 1.3 and the handshake

I cannot capture packets, but `s_client -msg` prints each handshake message. For TLS 1.3 (trimmed):

```
>>> Handshake, ClientHello
<<< Handshake, ServerHello
<<< Handshake, EncryptedExtensions
<<< Handshake, Certificate
<<< Handshake, CertificateVerify
<<< Handshake, Finished
>>> Handshake, Finished
<<< Handshake, NewSessionTicket
```

In words: the ClientHello lists protocol versions, ciphers, SNI and the client's key share. The ServerHello picks one and sends its key share, so both sides can derive keys; everything after it is already encrypted. The server then sends its certificate chain and a CertificateVerify, a signature proving it holds the private key. Both `Finished` messages confirm nobody altered the handshake. Per the docs, TLS 1.3 needs one round trip here, TLS 1.2 two; I did not measure it.

## ALPN

With the server started with `-alpn h2,http/1.1`, a client offering `-alpn h2,http/1.1` got `ALPN protocol: h2`. A client offering only `foo` got `tlsv1 alert no application protocol` (alert 120). That is {{< term "alpn" "ALPN" >}}: the protocol is chosen inside TLS, the topic of the next post.

## Mutual TLS

I made a client certificate (`extendedKeyUsage=clientAuth`, CN `demo-client`) from the same CA and started `s_server -CAfile ca.pem -Verify 1`. This is {{< term "mutual-tls" "mutual TLS" >}}:

```
# no client cert
SSL alert number 116  (tlsv13 alert certificate required)
server: peer did not return a certificate
# with -cert client.pem -key client.key
HTTP/1.0 200 ok
server: depth=0 CN=demo-client   verify return:1
```

Note that in TLS 1.3 the client's handshake appears to finish and the rejection arrives as an alert on the first read.

## A public site

`openssl s_client -connect example.com:443 -servername example.com` shows the chain (only subject lines, trimmed):

```
0 s:CN=example.com
1 s:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
2 s:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
3 s:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
```

Leaf, two intermediates, a root. Your system trusts the root; the server sends the rest. This chain can change at any time.

## A few things to watch

- Always set a SAN, with `IP:` entries for IP addresses.
- Never "fix" a verify error with `-k` or by skipping verification; add the CA instead.
- Keep CA keys private and certificates short-lived; my demo CA lasts 30 days.
- `s_client` and your language's TLS library may disagree (CN fallback). Test with the client you ship.
- Check which `openssl` you run: LibreSSL and OpenSSL differ.

## Exercise

Create a second server certificate whose SAN has only `DNS:demo.test`. Connect with `-verify_hostname demo.test` on `127.0.0.1`. Then use `-verify_hostname localhost` and explain both results.

## What's next

The next post is HTTP/2 and what changes. A later series covers TLS and x509 certificates in practice.
