+++
date = '2027-03-25T10:00:00+03:30'
draft = false
title = 'WebSocket'
description = 'WebSocket explained by hand on loopback: the upgrade handshake, masked frames, ping and close, then a Go hub with heartbeats and slow-client limits.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "websocket", "http", "go", "heartbeat", "backpressure"]
cover = { image = "/images/covers/net-websocket.png", alt = "WebSocket", hiddenInSingle = true }
+++

In [the previous post](/posts/net-http2/) we looked at HTTP/2. HTTP is still request and response, though: the server cannot speak first. {{< term "websocket" "WebSocket" >}} fixes that by turning one {{< term "tcp" "TCP" >}} connection into a two-way message channel. It starts as ordinary {{< term "http" "HTTP" >}}, as in [HTTP/1.1 by hand](/posts/net-http1-by-hand/), then the bytes change shape; the framing problem is the one from [a TCP server from scratch](/posts/net-sockets-tcp-from-scratch/).

> Everything ran on `127.0.0.1` with random ports (not printed), Go 1.26, macOS, `github.com/coder/websocket` v1.8.15. I did not run Linux. The machine was busy, so there are counts, no timings. The demo is a local example directory.

## The upgrade handshake

The client sends a normal GET with `Upgrade: websocket` and a random `Sec-WebSocket-Key`. The server proves it understood by returning `Sec-WebSocket-Accept`: base64 of the {{< term "sha-1" "SHA-1" >}} of the key plus a fixed GUID from RFC 6455. My hand-written server (stdlib only, it hijacks the connection) computed this for the RFC's example key `dGhlIHNhbXBsZSBub25jZQ==`, and a raw {{< term "socket" "socket" >}} client printed the real response:

```
"HTTP/1.1 101 Switching Protocols\r\n"
"Upgrade: websocket\r\n"
"Connection: Upgrade\r\n"
"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
"\r\n"
```

That matches the value in the RFC. The accept key is not security; it only shows the server understood the upgrade. After the blank line the connection is no longer HTTP ({{< term "http-upgrade" "HTTP Upgrade" >}}).

## One frame, byte by byte

I sent the text `Hello` with the RFC's mask key `37 fa 21 3d`:

```
client frame: 81 85 37 fa 21 3d 7f 9f 4d 51 58
byte0=10000001 (FIN=1 opcode=1)  byte1=10000101 (MASK=1 len=5)
mask key: 37 fa 21 3d  masked payload: 7f 9f 4d 51 58
server frame: 81 05 48 65 6c 6c 6f -> opcode=1 masked=false payload="Hello"
```

The first byte holds FIN (last fragment) and the opcode (1 is text). The second holds the MASK bit and a 7-bit length; 126 and 127 mean a 16-bit or 64-bit length follows. Every client frame must be masked: each payload byte is XORed with the mask key, so `0x48 ^ 0x37 = 0x7f`. Server frames are not masked, so the echo is plain `48 65 6c 6c 6f`.

## Ping, pong and close

Control frames use the same layout. I sent a ping with payload `hi` and got a pong back with the same payload. Then I sent a close with code 1000 and the reason `bye`:

```
ping sent; got: 8a 02 68 69 opcode=10 payload="hi"
close sent; got: 88 05 03 e8 62 79 65 opcode=8 code=1000 reason="bye"
after close, read: EOF
```

Close is a handshake: each side sends one, then the TCP connection ends. `0x03e8` is 1000, normal closure.

## A real server with a library

My hand-written server skips fragmentation, extensions and size limits, so use a library for real work. I used `coder/websocket` (the version above was fetched and pinned). An echo server is a loop of `Read` and `Write`, and `go test -race` passed:

```
TestEcho: echo: "hello"
TestEcho: close error: <nil>
```

## Broadcast with a hub

A hub keeps the connected clients and {{< term "fan-out" "fans out" >}} each message to all of them. Each client has its own writer goroutine and a bounded queue, so one slow client cannot block the rest. With 5 clients and 20 messages:

```
clients=5 messages=20 deliveries=100 evicted=0
```

Six runs with `-race` all passed.

## A client that disappears

A TCP connection can look open after the peer is gone. The server pings every 50 ms (the value is short only for the demo) and waits for a pong with a {{< term "deadline" "deadline" >}}. I connected 3 well-behaved clients and 1 raw socket that finished the handshake and then went silent:

```
connected: 4
after heartbeat: connected=3 ping_failures=1
```

The silent one was detected and dropped, the others stayed. This is a {{< term "heartbeat" "heartbeat" >}}. Production values are in seconds.

## A slow client

If a client does not read, TCP fills up, the writer blocks and the queue grows. An unbounded queue is a memory leak, so I used a queue of 256 messages and disconnect whoever overflows it. Three fast clients and one that connected but never read, 600 messages of 64 KiB:

```
fast clients=3 messages=600 delivered=1800 evicted=1
```

All 1800 messages reached the fast clients and exactly one client was evicted. This is {{< term "backpressure" "backpressure" >}} by dropping the client.

## WebSocket, SSE or polling?

My opinion, not a measurement:

- Plain polling or long requests when updates are rare and simplicity matters.
- {{< term "server-sent-events" "SSE" >}} when only the server pushes (feeds, progress); it is plain HTTP and reconnects by itself. I did not run an SSE demo here.
- WebSocket when both sides send often (chat, games, collaboration).

## A few things to watch

- Always bound the per-client queue and decide what happens on overflow.
- Add a heartbeat or read deadline; do not trust a quiet connection.
- Set a maximum message size.
- Check the `Origin` header for browser clients; I did not cover authentication here.
- Load balancers need to allow long-lived connections.

## Exercise

Change the hub to drop the oldest queued message instead of disconnecting. Then count what a slow client receives versus what was sent.

## What's next

The next post is "gRPC over HTTP/2".
