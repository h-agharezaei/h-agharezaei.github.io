+++
date = '2027-03-13T10:00:00+03:30'
draft = false
title = 'HTTP/2 and what changes'
description = 'HTTP/2 in Go on loopback: ALPN negotiation, 20 concurrent requests over one TCP connection, HPACK header bytes measured, and h2c compared with HTTP/1.1.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http2", "tls", "go", "hpack"]
cover = { image = "/images/covers/net-http2.png", alt = "HTTP/2 and what changes", hiddenInSingle = true }
+++

In the previous post, [TLS and certificates with openssl](/posts/net-tls-openssl/), the last stop was {{< term "alpn" "ALPN" >}}: the client and server pick the application protocol inside the TLS handshake. Now we see what they pick. HTTP/2 keeps the methods, status codes and headers of [HTTP/1.1](/posts/net-http1-by-hand/), but changes how they travel on the wire. The semantics stay the same, and the framing changes. It runs on one {{< term "tcp" "TCP" >}} connection, see [the TCP/IP model](/posts/net-tcp-ip-model/).

> Everything ran on loopback with a throwaway self-signed certificate (SAN `localhost` and `127.0.0.1`) generated inside the demo program; the demo is a local Go example. The machine was busy, so I publish counts and bytes only, no timings.

## Which protocol did we get?

Go's `net/http` serves HTTP/2 automatically over TLS and the default client uses it. The handler prints what the server saw:

```go
fmt.Fprintf(w, "proto=%s alpn=%q\n", r.Proto, r.TLS.NegotiatedProtocol)
```

To force HTTP/1.1 on the client, set `TLSNextProto` to an empty, non-nil map, which turns off the h2 upgrade:

```go
tr := &http.Transport{TLSClientConfig: cfg, TLSNextProto: map[string]func(string, *tls.Conn) http.RoundTripper{}}
```

Real output:

```
== default (h2 allowed)
client resp.Proto=HTTP/2.0  ALPN="h2"
server saw: proto=HTTP/2.0 alpn="h2"
== TLSNextProto empty (HTTP/1.1 only)
client resp.Proto=HTTP/1.1  ALPN=""
server saw: proto=HTTP/1.1 alpn=""
```

In the first run the client offered `h2` and `http/1.1`, and the server picked `h2`. In the second the client offered no h2, so no protocol was negotiated and HTTP/1.1 was used. Both used TLS 1.3 (version value `0x0304`).

## Twenty requests, one connection

HTTP/1.1 answers one request at a time per connection. While a response is slow, the next request on that connection waits, which is {{< term "head-of-line-blocking" "head-of-line blocking" >}}, so clients open several connections. HTTP/2 does {{< term "multiplexing" "multiplexing" >}}: each request is a numbered stream and their frames are interleaved on one connection.

To prove it, the server counts accepted TCP connections, and the `/barrier` handler holds every request until all 20 are in flight at the same time. The client fires 20 goroutines:

```
HTTP/2:   TCP connections=1,  requests in flight at once=20
HTTP/1.1: TCP connections=20, requests in flight at once=20
```

Same work, same client code. With HTTP/1.1 each concurrent request needed its own connection, and with it its own TCP and TLS handshake. Note that Go's HTTP/1.1 transport has no default limit on connections per host; browsers cap it at a small number per host (according to common practice, I did not test that), which is where "domain sharding" tricks came from.

## Headers: HPACK

Headers repeat on every request: cookie, user agent, accept. {{< term "hpack" "HPACK" >}} compresses them with a table both sides keep per connection, so a repeated header becomes a small index. I measured it honestly: the server counts the bytes it reads. A client sends 51 sequential `GET`s over one connection, each with a 400-byte cookie plus two more headers. I took the bytes after the first request (which includes the TLS handshake) and counted the next 50:

```
HTTP/2:   1953 bytes for 50 requests = 39.1 per request
HTTP/1.1: 30500 bytes for 50 requests = 610.0 per request
```

The counts include TLS record overhead and, for HTTP/2, small control frames, so treat them as an upper bound of the header cost. The ratio is large because the same big cookie travels as plain text every time in HTTP/1.1. This is one synthetic case; real traffic gains less.

## h2c: HTTP/2 without TLS

Browsers speak HTTP/2 only over TLS, but the protocol itself does not require it. The cleartext variant is called h2c. Since Go 1.24, `http.Protocols` can enable it on both sides:

```go
srv.Protocols = new(http.Protocols); srv.Protocols.SetHTTP1(true); srv.Protocols.SetUnencryptedHTTP2(true)
tr.Protocols = new(http.Protocols);  tr.Protocols.SetUnencryptedHTTP2(true)
```

```
client resp.Proto=HTTP/2.0; server saw proto=HTTP/2.0 tls=false
```

It is mostly useful between internal services, for example behind a proxy that already terminates TLS.

## What I did not run

- HTTP/3 and QUIC: it runs over UDP (see [UDP](/posts/net-udp-sockets/)) and I did not run it. As I understand the docs, it exists to remove TCP-level head-of-line blocking, because a lost packet in TCP stalls every HTTP/2 stream.
- Server push: the HTTP/2 spec has it, but as far as I know browsers have removed or disabled support. I did not test it.
- `curl --http2`: curl on this Mac is unreliable for TLS checks (see the previous post), so I did not use it.

## A few things to watch

- Check `resp.Proto` and `r.Proto` in your own services; a proxy in the middle may silently speak HTTP/1.1 to your backend.
- One connection means one TCP stream: a lost packet stalls all requests on it.
- Do not shard domains or bundle everything for HTTP/2 by habit; measure first.
- Limits like max concurrent streams exist per connection; do not assume unlimited parallelism.
- Do not change `TLSNextProto` unless you need HTTP/1.1; an empty map is how Go's docs say to disable h2.

## Exercise

Change the `/barrier` demo to 300 concurrent requests. How many TCP connections does HTTP/2 use now? Look up the server's maximum concurrent streams setting in the `net/http` docs and explain what you see.

## What's next

The next post is WebSocket.
