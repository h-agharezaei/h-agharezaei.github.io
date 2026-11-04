+++
date = '2027-03-01T10:00:00+03:30'
draft = false
title = 'TLS and certificates with openssl'
description = 'TLS and certificates with openssl on loopback: build a CA, sign a certificate with a SAN, read verification errors, TLS 1.2 vs 1.3, ALPN and mutual TLS.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tls", "openssl", "certificates", "mtls", "security"]
cover = { image = "/images/covers/net-tls-openssl.png", alt = "TLS and certificates with openssl", hiddenInSingle = true }
+++

You open a page, or call an API, and get something like this:

```
verify error:num=20:unable to get local issuer certificate
```

Most people have seen a message like that and not known what to do with it, so the usual reaction is to turn verification off. That is a pity, because every one of these errors has a precise meaning, and it takes only a short experiment to learn them. Most {{< term "tls" "TLS" >}} pain is not cryptography, it is certificates and error messages.

The requests from [HTTP/1.1 by hand](/posts/net-http1-by-hand/) crossed a plain socket as readable text, so anyone on the path could read or change them. TLS sits between TCP and HTTP (see [the TCP/IP model](/posts/net-tcp-ip-model/) and [TCP connections](/posts/net-tcp-handshake-states/)) and gives the connection three things: **encryption** (nobody on the path can read it), **integrity** (nobody can change it unnoticed), and **authentication** (you know which server you are talking to). The third one is where certificates come in, and it is the source of nearly every error message.

The idea in short: a server holds a private key and a **certificate**, a document that says "this public key belongs to the name `localhost`", signed by someone the client trusts. During the handshake the server shows its certificate and proves it holds the matching private key. The client checks the signature, the name and the dates. If all three pass, the connection continues; if one fails, you get an error that says which.

To learn what those checks mean, we build the whole thing ourselves with `openssl`: our own certificate authority, a server certificate, a test server and a test client. Then we break it on purpose, and read each error.

> Everything ran on `127.0.0.1` with throwaway keys and certificates that I generated in a scratch directory (`<tmp>`), so nothing personal is in the output. I used Homebrew's `/opt/homebrew/bin/openssl` (OpenSSL 3.6.4); macOS's `/usr/bin/openssl` is LibreSSL 3.3.6 and has different options. Go is 1.27.3 on macOS (Darwin, arm64). The port is shown as `PORT` and was random. Because I regenerated the certificates, dates and fingerprints differ from the original run. No packet capture was possible (no root).

## A CA and a server certificate

A {{< term "certificate-authority" "certificate authority" >}} (CA) is nothing magical: it is a key plus a certificate that signs itself. Clients that choose to trust that certificate will then trust everything it signs. We make one:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 30 -subj "/CN=Demo Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" -out ca.pem
```

The first command creates a private key on the P-256 elliptic curve. The second makes a self-signed certificate valid for 30 days, whose `CN` (common name) is `Demo Root CA`. `CA:TRUE` says this certificate may sign other certificates, and `keyCertSign` says that is what its key is for.

Now the server gets its own key, a **certificate signing request** (CSR: "please certify this key for this name"), and the CA signs it:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key
openssl req -new -key server.key -subj "/CN=localhost" -out server.csr
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -days 7 -sha256 -extfile ext.cnf -out server.pem
```

`ext.cnf` holds the important part, the {{< term "subject-alt-name" "SubjectAltName" >}}, the list of names this certificate is valid for:

```
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
```

`CA:FALSE` means this certificate cannot sign others, and `serverAuth` says it may identify a TLS server. The last line says it is valid for the DNS name `localhost` and for the IP address `127.0.0.1`.

Why not just use the common name? Because clients match the host name against the SAN list, and many modern clients ignore the common name. To see the difference I made a second certificate with the same key but no SAN (`nosan.pem`, with `basicConstraints=CA:FALSE` as its only extension) and tried it. OpenSSL's `-verify_hostname localhost` still printed `Verification: OK`, because it falls back to the common name. A Go client (`crypto/tls`) refused it:

```
error: tls: failed to verify certificate: x509: certificate relies on legacy Common Name field, use SANs instead
```

So the same certificate is "fine" for one tool and "broken" for another. Always set the SAN.

Here are the main fields of the real certificate, from `openssl x509 -in server.pem -noout -text` (an {{< term "x509-certificate" "X.509" >}} certificate; I picked these lines and joined each field with its value):

```
Issuer: CN=Demo Root CA
Not Before: Nov  4 16:50:43 2026 GMT
Not After : Nov 11 16:50:43 2026 GMT
Subject: CN=localhost
Public Key Algorithm: id-ecPublicKey
X509v3 Extended Key Usage: TLS Web Server Authentication
X509v3 Subject Alternative Name: DNS:localhost, IP Address:127.0.0.1
```

Read it like an ID card: who vouches for it (`Issuer`), whom it is about (`Subject`), when it is valid, what kind of key it carries, and what it may be used for. These dates are from this run and differ every time. `openssl verify -CAfile ca.pem server.pem` prints `server.pem: OK`.

## Connect and verify

Now we need a server and a client. `openssl s_server` is a small TLS test server, and `-www` makes it answer a web request with a status page. I started it on a random port:

```
openssl s_server -accept PORT -cert server.pem -key server.key -www
```

Then `openssl s_client` connects as a client. `-CAfile ca.pem` says which CA to trust, and `-verify_hostname` asks it to check the name too. Its full output is long, so I kept only the lines about verification:

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

The two `depth` lines are the {{< term "certificate-chain" "certificate chain" >}} being checked from the top: depth 1 is our CA, depth 0 is the server's own certificate. `Verification: OK` and `Verified peername: localhost` mean the signature, the dates and the name all passed. The `New` line is the result of the negotiation: TLS 1.3 with the cipher `TLS_AES_256_GCM_SHA384`. Forcing `-tls1_2` instead gave `TLSv1.2` and `ECDHE-ECDSA-AES256-GCM-SHA384`. A Go client (a small program using `crypto/tls` with `ca.pem` as its trusted CA) connected to the same server and printed `ok: version=TLS 1.3 cipher=TLS_AES_128_GCM_SHA256`; the two sides can pick different ciphers, because each has its own preferences.

`-servername` sends {{< term "sni" "SNI" >}} (server name indication): the name the client wants, sent inside the handshake. It lets one IP address and port serve many certificates, one per name.

I also tried `curl --cacert ca.pem https://localhost:PORT/`. On this Mac, `/usr/bin/curl` (8.7.1) uses Apple's SecureTransport and did not behave like a verifying client: it exited with status 0 even without `--cacert`, and with `--cacert` the `%{ssl_verify_result}` write-out variable printed 20. I do not trust it for this demo, so I show only `openssl` and Go results.

## The failures, for real

Now to break it. Each of these is a real run against our test server, and I show the relevant lines of each. First, the client does not know our CA, because I left out `-CAfile`:

```
# 1. client does not know our CA
verify error:num=20:unable to get local issuer certificate
verify error:num=21:unable to verify the first certificate
Verification error: unable to verify the first certificate
Verify return code: 21 (unable to verify the first certificate)
```

The certificate was signed by "Demo Root CA", but this client has no such CA in its trusted list, so it cannot follow the signature up to anything it trusts. This is the error from the top of the post. The fix is to trust the right CA, never to turn verification off. (Go prints the same problem as `x509: certificate signed by unknown authority`; I ran that too, with the wrong certificate as its CA.)

Second, the certificate is valid, but we ask for a name that is not in its SAN (`-verify_hostname example.org`):

```
# 2. name not in the SAN
verify error:num=62:hostname mismatch
Verify return code: 62 (hostname mismatch)
```

The signature and dates are fine, but the certificate is not for that name. This check protects you from a valid certificate that belongs to a different site.

Third, a certificate whose dates have passed. I made one with `openssl x509 -req ... -not_before 20260101000000Z -not_after 20260102000000Z` (these options exist in OpenSSL 3.6) and ran a server with it:

```
# 3. expired certificate
verify error:num=10:certificate has expired
Verify return code: 10 (certificate has expired)
```

`openssl verify -CAfile ca.pem expired.pem` reports the same error 10. Certificates expire on purpose, so that a stolen or forgotten one does not stay valid forever.

## TLS 1.2, 1.3 and the handshake

What happens inside the connection before the first byte of HTTP? I cannot capture packets here, but `s_client -msg` prints each handshake message. For TLS 1.3, keeping only the lines for handshake messages and alerts (`[length ...]` is the message size in bytes, in hexadecimal):

```
>>> TLS 1.3, Handshake [length 05ff], ClientHello
<<< TLS 1.3, Handshake [length 04ba], ServerHello
<<< TLS 1.3, Handshake [length 0006], EncryptedExtensions
<<< TLS 1.3, Handshake [length 01cc], Certificate
<<< TLS 1.3, Handshake [length 0050], CertificateVerify
<<< TLS 1.3, Handshake [length 0034], Finished
>>> TLS 1.3, Handshake [length 0034], Finished
>>> TLS 1.3, Alert [length 0002], warning close_notify
```

`>>>` is what the client sent and `<<<` what the server sent. In words:

- **ClientHello:** the client says which protocol versions and ciphers it supports, which name it wants (SNI), and includes its half of a key exchange (a "key share").
- **ServerHello:** the server picks one option and sends its own key share. Now both sides can compute the same secret keys without ever sending them, and everything after this message is encrypted.
- **Certificate:** the server's certificate. Our server sends only its own, because the client already has the CA. The `Certificate` message is 0x1cc = 460 bytes long here.
- **CertificateVerify:** a {{< term "digital-signature" "signature" >}} over the handshake so far, made with the private key. This is the proof that the server really holds the key that the certificate names. A stolen certificate alone is useless without it.
- **Finished** (both directions): each side confirms that nobody altered the handshake.
- **close_notify:** a polite goodbye from the client, because my command ended the connection.

I did not see a `NewSessionTicket` message (a ticket for faster reconnection) in this run. According to RFC 8446, TLS 1.3 needs one round trip for the handshake and TLS 1.2 needs two; I did not measure it.

## ALPN

The same handshake also settles which protocol will run inside TLS, using {{< term "alpn" "ALPN" >}}. I started the server with `-alpn h2,http/1.1` and tried three clients:

```
client offers h2,http/1.1    -> ALPN protocol: h2
client offers http/1.1 only  -> ALPN protocol: http/1.1
client offers only foo       -> alert number 120: tlsv1 alert no application protocol
```

The client lists what it can speak, and the server picks. A client with no match in common is refused with an alert, and a client that offers no ALPN at all just gets "No ALPN negotiated". `h2` is HTTP/2, the topic of the next post.

## Mutual TLS

So far only the server proved who it is. In {{< term "mutual-tls" "mutual TLS" >}} the client has to present a certificate too. I made a client certificate (`extendedKeyUsage=clientAuth`, common name `demo-client`) from the same CA and started the server with `-CAfile ca.pem -Verify 1`:

```
# no client cert
client: alert number 116 (tlsv13 alert certificate required)
server: peer did not return a certificate
# with -cert client.pem -key client.key
HTTP/1.0 200 ok
server: depth=0 CN=demo-client   verify return:1
```

Without a certificate the server refuses and tells the client why. With one, the server verified it against the same CA, logged the name `demo-client`, and the request went through. In TLS 1.3 the client's side of the handshake may appear to finish before the server rejects it, so the rejection arrives as an alert when the client first reads.

## A public site

To see how a real chain looks, `openssl s_client -connect example.com:443 -servername example.com` shows the certificates the server sends. Here are only their subject (`s:`) and issuer (`i:`) lines, which are public:

```
0 s:CN=example.com
   i:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
1 s:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
   i:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
2 s:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
   i:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
3 s:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
   i:C=GB, ST=Greater Manchester, L=Salford, O=Comodo CA Limited, CN=AAA Certificate Services
```

Each certificate's issuer is the next certificate's subject: the leaf for `example.com`, two intermediate CAs, and the SSL.com root, which here is itself signed by an older root. I read that last one as a cross-signature, which lets older clients that only know the older root still build a chain. The verification result was `OK` with this OpenSSL. Your system trusts a root and the server sends the rest, and this chain can change at any time.

## Certificate mistakes to avoid

- Always set a SAN, with `IP:` entries for IP addresses.
- Never "fix" a verify error with `-k` or by skipping verification. Add the CA to the trusted list instead, as we did with `-CAfile`.
- Keep CA keys private and certificates short-lived. My demo CA lasts 30 days.
- `s_client` and your language's TLS library may disagree, as the common-name fallback showed. Test with the client you ship.
- Check which `openssl` you run: LibreSSL and OpenSSL differ in options and output.

## Exercise

Create a second server certificate whose SAN has only `DNS:demo.test`. Connect with `-verify_hostname demo.test` on `127.0.0.1`. Then use `-verify_hostname localhost` and explain both results.

## What's next

The next post is "HTTP/2 and what changes", the protocol that ALPN picked as `h2` above. A later series covers TLS and x509 certificates in practice.
