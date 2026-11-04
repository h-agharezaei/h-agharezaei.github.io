+++
date = '2027-03-25T10:00:00+03:30'
draft = false
title = 'WebSocket'
description = 'WebSocket explained by hand on loopback: the upgrade handshake, masked frames, ping and close, then a Go hub with heartbeats and slow-client limits.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "websocket", "http", "go", "heartbeat", "backpressure"]
cover = { image = "/images/covers/net-websocket.png", alt = "WebSocket", hiddenInSingle = true }
+++

Think of a chat page. A message from someone else should appear on your screen the moment it is sent. But HTTP works like a question and an answer: the client asks, the server answers, and the server cannot speak unless it was asked, even with the HTTP/2 of [the previous post](/posts/net-http2/). The workaround is to ask again and again ("any news?"), which wastes requests and still shows the message late.

{{< term "websocket" "WebSocket" >}} solves this by turning one {{< term "tcp" "TCP" >}} connection into a two-way channel where either side can send a message at any time. The idea has two steps. First the client starts with an ordinary {{< term "http" "HTTP" >}} request, as in [HTTP/1.1 by hand](/posts/net-http1-by-hand/), asking "can we switch protocols?". If the server agrees, it answers once, and from that moment the same connection no longer carries HTTP. It carries small binary **frames**, each one a message or a control signal. TCP is a stream without message boundaries (the problem from [a TCP server from scratch](/posts/net-sockets-tcp-from-scratch/)), so the frames are WebSocket's own answer to the framing problem.

In this post we do both steps by hand, at the byte level, and then use a library for the parts that matter in production: broadcasting, dead clients and slow clients.

> Everything ran on `127.0.0.1` with random ports (not printed), with Go 1.27.3 on macOS (Darwin, arm64) and `github.com/coder/websocket` v1.8.15 (the original run used Go 1.26). I did not run Linux. The machine was busy, so there are counts, no timings. The demo is a local example directory. One small test that I used for the length bytes below is not in that directory; I ran it in a scratch copy.

## The upgrade handshake

The client sends a normal GET with two special headers, `Upgrade: websocket` and `Connection: Upgrade`, plus a version and a random `Sec-WebSocket-Key`. Here is the request that the demo's raw client writes:

```
GET /ws HTTP/1.1
Host: 127.0.0.1
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

The server proves that it understood the upgrade by returning `Sec-WebSocket-Accept`. Its value is a small calculation: take the key exactly as sent, glue a fixed GUID from RFC 6455 behind it, compute the {{< term "sha-1" "SHA-1" >}} hash, and write the result in base64. You can check it in a terminal, with the key above (the RFC's own example key):

```
$ printf '%s' 'dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11' | openssl sha1 -binary | base64
s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

My hand-written server (stdlib only, it hijacks the connection from `net/http`) does the same in a function called `AcceptKey`, and a raw {{< term "socket" "socket" >}} client printed what really came back. The first line below is the demo calling that function, and the rest is the response:

```
accept key for RFC example: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
"HTTP/1.1 101 Switching Protocols\r\n"
"Upgrade: websocket\r\n"
"Connection: Upgrade\r\n"
"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
"\r\n"
```

All three agree, and they match the value printed in the RFC. Status `101` means "switching protocols". The accept key is not security; it only shows that the server understood a WebSocket upgrade and is not some HTTP server that echoed the headers. After the empty line the connection is no longer HTTP ({{< term "http-upgrade" "HTTP Upgrade" >}}): everything that follows is frames.

## One frame, byte by byte

A frame has a small header followed by the payload. The first byte holds a **FIN** bit (this is the last fragment of the message) and a 4-bit **opcode** (what kind of frame it is: 1 is text, 2 is binary, 8 is close, 9 is ping, 10 is pong). The second byte holds a **MASK** bit and a 7-bit length. If the length is 126, the next two bytes hold the real length; if it is 127, the next eight. If the MASK bit is set, a 4-byte mask key follows, and then the payload.

Let us send the text `Hello`, with the RFC's mask key `37 fa 21 3d`. The demo prints the frame and splits it:

```
client frame: 81 85 37 fa 21 3d 7f 9f 4d 51 58
byte0=10000001 (FIN=1 opcode=1)  byte1=10000101 (MASK=1 len=5)
mask key: 37 fa 21 3d  masked payload: 7f 9f 4d 51 58
server frame: 81 05 48 65 6c 6c 6f -> opcode=1 masked=false payload="Hello"
```

- `81` is `1000 0001`: FIN is 1 and the opcode is 1, a text frame.
- `85` is `1000 0101`: MASK is 1 and the length is 5.
- `37 fa 21 3d` is the mask key. Every client frame must be masked: each payload byte is XORed with a key byte, cycling through the four. For the first letter, `H` is `0x48` and `0x48 ^ 0x37 = 0x7f`, the first masked byte. Next, `e` is `0x65` and `0x65 ^ 0xfa = 0x9f`, and so on. The fifth letter wraps around to the first key byte: `o` is `0x6f` and `0x6f ^ 0x37 = 0x58`.
- The server's echo is `81 05 48 65 6c 6c 6f`: server frames are not masked, so the payload is plain text bytes `48 65 6c 6c 6f`, which is `Hello`.

Why mask at all, if it is not encryption (the key is sent right next to the data)? According to RFC 6455 it protects the proxies and caches between a browser and a server, which could otherwise be confused by bytes that a web page chose freely; the mask makes those bytes unpredictable to the page. The server must reject unmasked client frames, and my demo server does.

For the length rule, I ran the demo's `EncodeFrame` on payloads of different sizes and looked at the first bytes (this small test is not part of the demo directory):

```
payload 125 bytes -> first bytes: 81 7d 00 00
payload 126 bytes -> first bytes: 81 7e 00 7e
payload 300 bytes -> first bytes: 81 7e 01 2c
```

Up to 125 bytes the length lives in the second byte (`7d` is 125). From 126 on, the second byte becomes `7e` (126) and the next two bytes hold the length: `00 7e` is 126 and `01 2c` is 300. (The trailing `00 00` in the first line are already payload bytes.)

## Ping, pong and close

Control frames use the same layout. I sent a ping with the payload `hi` and got a pong back (opcode 10, `0x8a` is FIN plus 10) with the same payload. Then I sent a close frame whose payload is a status code followed by a reason: 1000 and `bye`:

```
ping sent; got: 8a 02 68 69 opcode=10 payload="hi"
close sent; got: 88 05 03 e8 62 79 65 opcode=8 code=1000 reason="bye"
after close, read: EOF
```

Close is a handshake: one side sends a close frame, the other answers with one, and then the TCP connection ends. In the answer, `88` is FIN plus opcode 8, the length 5 is a 2-byte code and three letters, `03 e8` is 1000 (`0x03e8`), the code for normal closure, and `62 79 65` is `bye`. The last line shows that the server then closed the TCP connection: the client's next read returned EOF.

## A real server with a library

My hand-written server skips fragmentation (messages split into several frames), extensions and size limits, so use a library for real work. I used `coder/websocket` (the version above was fetched and pinned in `go.mod`). An echo server is a loop of `Read` and `Write`. The test passed, also with `-race` (the lines are what `go test -v` printed from the test's `t.Logf`):

```
ws_test.go:72: echo: "hello"
ws_test.go:73: close error: <nil>
```

## Broadcast with a hub

A chat needs one more piece: when one message arrives, it must go to everybody. A **hub** keeps the connected clients and {{< term "fan-out" "fans out" >}} each message to all of them. The trap is a slow client: if the hub writes to clients one by one, a client that does not read would block everyone behind it. So each client gets its own writer goroutine and a bounded queue, and `Broadcast` only puts the message in each queue. With 5 clients and 20 messages:

```
ws_test.go:113: clients=5 messages=20 deliveries=100 evicted=0
```

20 messages to 5 clients is 100 deliveries, and nobody was evicted. I ran the whole test suite with `-race` four times in a row on this run and all four passed.

## A client that disappears

A TCP connection can look open long after the other side is gone, for example when a phone loses its network. Nothing is sent, so nothing tells you. The fix is to ask: the server sends a ping every 50 ms (the value is short only for the demo) and waits for a pong with a {{< term "deadline" "deadline" >}}. If no pong comes, it drops the client. I connected 3 well-behaved clients and 1 raw socket that finished the handshake and then went silent:

```
ws_test.go:149: connected: 4
ws_test.go:153: after heartbeat: connected=3 ping_failures=1
```

The silent one was detected and dropped, and the three others stayed connected through more rounds of pings. This is a {{< term "heartbeat" "heartbeat" >}}. Production values are in seconds, not milliseconds.

## A slow client

The opposite problem is a client that is alive but does not read. TCP's buffers fill up, the server's writer blocks, and the queue for that client grows. An unbounded queue is a memory leak, so the hub uses a queue of 256 messages and disconnects whoever overflows it. The test has three fast clients and one that connected but never reads, and the hub sends 600 messages of 64 KiB (the demo clients raise the library's read limit so that they can receive messages that large):

```
ws_test.go:190: fast clients=3 messages=600 delivered=1800 evicted=1 still_connected=0
```

All 1800 messages (3 clients times 600) reached the fast clients and exactly one client was evicted, the one that never read. `still_connected=0` is printed after the fast clients had read everything and closed, and the slow one had already been dropped. This is {{< term "backpressure" "backpressure" >}} by dropping the client.

## WebSocket, SSE or polling?

My opinion, not a measurement:

- Plain polling or long requests when updates are rare and simplicity matters.
- {{< term "server-sent-events" "SSE" >}} when only the server pushes (feeds, progress). It is plain HTTP and reconnects by itself. I did not run an SSE demo here.
- WebSocket when both sides send often (chat, games, collaboration).

## Before you ship a WebSocket server

- Always bound the per-client queue and decide what happens on overflow. Without a bound, one stuck client can exhaust your memory.
- Add a heartbeat or a read deadline. A quiet connection is not necessarily a healthy one.
- Set a maximum message size, so a single huge frame cannot be used against you.
- Check the `Origin` header for browser clients. I did not cover authentication here.
- Load balancers and proxies need to allow long-lived connections and the upgrade headers.

## Exercise

Change the hub to drop the oldest queued message instead of disconnecting. Then count what a slow client receives versus what was sent.

## What's next

The next post is "gRPC over HTTP/2". WebSocket leaves HTTP after the handshake. gRPC stays inside HTTP/2 and gets streaming from its streams instead.
