+++
date = '2027-03-13T10:00:00+03:30'
draft = false
title = 'HTTP/2 and what changes'
description = 'HTTP/2 in Go on loopback: ALPN negotiation, 20 concurrent requests over one TCP connection, HPACK header bytes measured, and h2c compared with HTTP/1.1.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http2", "tls", "go", "hpack"]
cover = { image = "/images/covers/net-http2.png", alt = "HTTP/2 and what changes", hiddenInSingle = true }
+++

Imagine one connection and two requests. The first asks for something slow, a report that takes a few hundred milliseconds to produce. The second asks for something instant. You write both on the same connection at once. Which answer do you get first?

With HTTP/1.1 you get the slow one first, because a connection delivers responses in the order of the requests, and the instant answer has to wait behind it. HTTP/2 was designed to remove that wait. In this post we send exactly these two requests with raw bytes on both protocols, and then look at what HTTP/2 puts on the wire.

The one-sentence idea: HTTP/2 keeps everything you know from [HTTP/1.1](/posts/net-http1-by-hand/) (methods, paths, status codes, headers) but changes how it is carried. Instead of a text message per request, the connection carries small binary pieces called **frames**, and every frame is labelled with the number of the request it belongs to, called a **stream**. Frames of different streams can be mixed freely on one {{< term "tcp" "TCP" >}} connection (see [the TCP/IP model](/posts/net-tcp-ip-model/)), so a slow answer no longer blocks a fast one. Headers are also compressed. And {{< term "alpn" "ALPN" >}}, the last stop of [TLS and certificates with openssl](/posts/net-tls-openssl/), is how the two sides agree to use it.

> Everything ran on loopback with Go 1.27.3 and Python 3.14 on macOS (Darwin, arm64). The original demo (a local Go example, written for Go 1.26) uses a throwaway self-signed certificate (SAN `localhost` and `127.0.0.1`) generated inside the program. For the frame-level parts I wrote two small extra programs, a Go server and a Python raw-socket client, that are not in that demo directory. I ran them from a scratch copy. The machine was busy, so I publish counts and bytes only, no timings.

## Slow first, fast second

The extra server has two handlers: `/slow` sleeps 300 milliseconds and answers `slow`, and `/fast` answers `fast` at once. It speaks HTTP/1.1 and also cleartext HTTP/2 (more on that below), so the same server serves both experiments. The client writes both requests in one go, `/slow` first. For HTTP/1.1 that is two ordinary requests glued together, and this is what came back:

```
HTTP/1.1, both requests written at once; bodies in the order they came back:
  first body: slow, second body: fast
```

As expected: the server handles them in order on that connection, so `fast` waits for `slow`. This is {{< term "head-of-line-blocking" "head-of-line blocking" >}}: one slow item at the front of a queue holds up everything behind it. Real HTTP/1.1 clients rarely send requests this way; they open several connections instead, which has a cost we will measure shortly.

Now the same two requests over HTTP/2, and here the bytes matter. To build them by hand we need to know what a frame looks like. Every HTTP/2 frame starts with a 9-byte header: 3 bytes of payload length, 1 byte of type, 1 byte of flags, and 4 bytes for the stream number (the top bit is reserved). The connection starts with a fixed 24-byte greeting from the client, `PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n`, followed by a `SETTINGS` frame. Here are the helpers of my client:

```python
def frame(ftype, flags, stream, payload=b""):
    return struct.pack(">I", len(payload))[1:] + bytes([ftype, flags]) + struct.pack(">I", stream) + payload

s.sendall(b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n" + frame(4, 0, 0))   # greeting + empty SETTINGS (type 4)
```

The empty `SETTINGS` frame is these nine bytes, `00 00 00 | 04 | 00 | 00 00 00 00`: length 0, type 4 (SETTINGS), no flags, stream 0. Stream 0 is the connection itself, used for messages that are not about any one request.

A request is a `HEADERS` frame (type 1). Its payload is the header block, compressed with {{< term "hpack" "HPACK" >}}, which we will decode shortly. For now: `82` and `86` mean `:method GET` and `:scheme http`, and the path and host are written as short literal strings. The client sends `/slow` on stream 1 and `/fast` on stream 3 (a client uses odd stream numbers), with flags `0x05`, which is END_STREAM (no body follows) plus END_HEADERS (the header block is complete):

```python
s.sendall(frame(1, 0x05, 1, request("/slow")) + frame(1, 0x05, 3, request("/fast")))
```

These are the frames the server sent back, in the order they arrived (`flags=0x04` on a response means END_HEADERS and `0x01` means END_STREAM; I cut the header block of stream 3 for width):

```
HTTP/2: stream 1 = /slow, stream 3 = /fast; frames from the server, in arrival order:
  SETTINGS flags=0x00 stream=0 len=36
  SETTINGS flags=0x01 stream=0 len=0
  WINDOW_UPDATE flags=0x00 stream=0 len=4
  HEADERS  flags=0x04 stream=3 len=49 block=88 5f 92 49 7c a5 8a e8 19 aa fb 50 ...
  DATA     flags=0x01 stream=3 len=4 data=b'fast'
  HEADERS  flags=0x04 stream=1 len=4 block=88 c0 bf be
  DATA     flags=0x01 stream=1 len=4 data=b'slow'
```

Read it from the top:

- The first `SETTINGS` frame (36 bytes, which is six 6-byte settings according to RFC 9113) is the server announcing its own limits. The second, with flags `0x01` (ACK) and no payload, acknowledges ours. `WINDOW_UPDATE` on stream 0 is a flow-control message; I did not look into its exact content.
- Then the point of the experiment. The answer for **stream 3** (`/fast`) arrives first: its `HEADERS` and its `DATA` with the body `fast`. About 300 milliseconds later the answer for **stream 1** (`/slow`) follows. The slow request did not hold up the fast one, even though it was sent first. That is {{< term "multiplexing" "multiplexing" >}}.
- I ran this several times. The order of the stream frames was the same each time, while the order of the three connection-level frames at the top changed between runs. The header block of stream 3 changed slightly in length between runs (48 to 50 bytes), because it contains the `Date` header.

The fast answer's frames were delivered while the slow request was still running, on one TCP connection. The cost of that is hidden in the TCP layer, and we will come back to it.

## Twenty requests, one connection

What does this change for a client that wants twenty things at once? With HTTP/1.1 it needs twenty connections, and each costs a TCP handshake and a TLS handshake. With HTTP/2 it can use one. The first demo is the original one from this post, a Go program with its own server and client. Go's `net/http` serves HTTP/2 automatically over TLS and the default client uses it. First, which protocol did we get? The handler prints what the server saw:

```go
fmt.Fprintf(w, "proto=%s alpn=%q tls=%x\n", r.Proto, r.TLS.NegotiatedProtocol, r.TLS.Version)
```

To force HTTP/1.1 on the client, set `TLSNextProto` to an empty, non-nil map, which turns off the h2 upgrade:

```go
tr := &http.Transport{TLSClientConfig: &tls.Config{RootCAs: pool}, TLSNextProto: map[string]func(string, *tls.Conn) http.RoundTripper{}}
```

The real output of the demo, first the two protocol lines of each run:

```
== default (h2 allowed)
client resp.Proto=HTTP/2.0  ALPN="h2"
server saw: proto=HTTP/2.0 alpn="h2" tls=304
== TLSNextProto empty (HTTP/1.1 only)
client resp.Proto=HTTP/1.1  ALPN=""
server saw: proto=HTTP/1.1 alpn="" tls=304
```

In the first run the client offered `h2` and `http/1.1`, and the server picked `h2`. In the second the client offered no h2, so no protocol was negotiated and HTTP/1.1 was used. Both used TLS 1.3 (`tls=304` is the version value `0x0304`).

The second part of the demo counts connections. The server counts the TCP connections it accepts, and its `/barrier` handler holds every request until all 20 are in flight at the same time (or gives up after 2 seconds). The client fires 20 goroutines. These are the real lines for both runs, picked out of the full output (which also has the byte counts we use below):

```
== default (h2 allowed)
20 concurrent requests: TCP connections in total (incl. the first request)=1, max requests in flight at once=20
== TLSNextProto empty (HTTP/1.1 only)
20 concurrent requests: TCP connections in total (incl. the first request)=20, max requests in flight at once=20
```

Same work, same client code. With HTTP/2 all 20 requests were in flight at once on the one connection that the first request had opened. With HTTP/1.1 each concurrent request needed its own connection, and with it its own TCP and TLS handshake. Go's HTTP/1.1 transport has no default limit on connections per host, so it opened 20. Browsers usually cap the number of connections per host, which is where tricks like "domain sharding" came from; I did not test that.

## Headers: HPACK

Headers repeat on every request: cookie, user agent, accept. In HTTP/1.1 they are sent in full each time. {{< term "hpack" "HPACK" >}} compresses them with a table that both sides keep for the whole connection. A header sent once can be referred to afterwards by its number in the table, which costs one byte.

We can see this with the raw client. It sends two requests on one connection, each with a 104-byte `cookie` header. The first one writes the cookie in full and asks the server to remember it (a "literal with incremental indexing", whose first byte is `0x60`: the cookie header name is entry 32 of HPACK's built-in table). The second request just writes `be`, which is binary `1011 1110`: the leading 1 means "an entry of the table", and the rest, 62, is the first slot of the connection's own table:

```
request header blocks: first 134 bytes, second 29 bytes
cookie value is 104 bytes
  (the same SETTINGS and WINDOW_UPDATE frames as before are left out here)
  DATA     flags=0x01 stream=1 len=24 data=b'cookie header: 104 bytes'
  DATA     flags=0x01 stream=3 len=24 data=b'cookie header: 104 bytes'
```

The first header block is 134 bytes, mostly the cookie. The second is 29 bytes, and 28 of them are the unchanged parts (method, scheme, path, host); the whole 104-byte cookie became one byte. And the server handler confirms it understood: both streams were answered with `cookie header: 104 bytes` (the two answers can arrive in either order; the order differed between my runs).

HPACK also works in the other direction, which you could see in the previous output. The first response on stream 3 is 49 bytes: `88` is `:status 200` (entry 8 of the built-in table), and the other headers (`content-type`, `content-length`, `date`) are written out as literals and added to the table. The second response, on stream 1, is `88 c0 bf be`: four bytes. `c0`, `bf` and `be` are table entries 64, 63 and 62, which are exactly those three headers, newest first. The server did not repeat them, it only pointed to them.

The original demo measures the same effect in bytes with real requests. The server counts the bytes it reads, and a client sends 51 sequential `GET`s over one connection, each with a 400-byte cookie plus two more headers. I took the bytes after the first request (which includes the TLS handshake) and counted the next 50. Again the real lines of the demo, picked from the full output:

```
== default (h2 allowed)
connections=1; first request (incl. TLS handshake) 2123 bytes; next 50 requests: 1953 bytes total, 39.1 per request
== TLSNextProto empty (HTTP/1.1 only)
connections=1; first request (incl. TLS handshake) 2187 bytes; next 50 requests: 30500 bytes total, 610.0 per request
```

The counts include TLS record overhead and, for HTTP/2, small control frames, so treat them as an upper bound of the header cost. The ratio is large because the same big cookie travels as plain text every time in HTTP/1.1. This is one synthetic case, and real traffic gains less.

## h2c: HTTP/2 without TLS

Browsers speak HTTP/2 only over TLS, but the protocol itself does not require it. The cleartext variant is called h2c, and it is what the raw-bytes experiments above used: the client simply starts with the `PRI * HTTP/2.0` greeting. Since Go 1.24, `http.Protocols` can enable it on both sides:

```go
srv.Protocols = new(http.Protocols); srv.Protocols.SetHTTP1(true); srv.Protocols.SetUnencryptedHTTP2(true)
tr.Protocols = new(http.Protocols);  tr.Protocols.SetUnencryptedHTTP2(true)
```

```
== h2c (no TLS): client resp.Proto=HTTP/2.0; server saw proto=HTTP/2.0 tls=false
```

It is mostly useful between internal services, for example behind a proxy that already terminates TLS.

## What HTTP/2 does not fix

One TCP connection carries all the streams, and TCP delivers bytes in order. If one packet is lost, TCP holds back everything after it until the packet is resent, and that stalls every stream on the connection, even streams whose frames had already arrived. That is head-of-line blocking again, one layer down. Loopback does not lose packets and I cannot capture or drop packets here, so I did not demonstrate this; it is how I understand the documentation.

## What I did not run

- HTTP/3 and QUIC: it runs over UDP (see [UDP and how it differs from TCP](/posts/net-udp-sockets/)) and I did not run it. As I understand the docs, it exists to remove that TCP-level blocking, because each stream is handled independently.
- Server push: the HTTP/2 spec has it, but as far as I know browsers have removed or disabled support. I did not test it.
- `curl --http2`: curl on this Mac is unreliable for TLS checks (see the previous post), so I did not use it.

## Assumptions to check

- Check `resp.Proto` and `r.Proto` in your own services. A proxy in the middle may silently speak HTTP/1.1 to your backend.
- One connection means one TCP stream: a lost packet stalls all requests on it.
- Do not shard domains or bundle everything for HTTP/2 by habit. Measure first.
- Limits like the maximum number of concurrent streams exist per connection, and the server announces them in its `SETTINGS` frame. Do not assume unlimited parallelism.
- Do not change `TLSNextProto` unless you need HTTP/1.1. An empty map is how Go's docs say to disable h2.

## Exercise

Change the `/barrier` demo to 300 concurrent requests. How many TCP connections does HTTP/2 use now? Look up the server's maximum concurrent streams setting in the `net/http` docs and explain what you see.

## What's next

The next post is "WebSocket". HTTP/2 lets many requests share a connection, but every exchange still starts with a request from the client. WebSocket is the way the server finally gets to speak first.
