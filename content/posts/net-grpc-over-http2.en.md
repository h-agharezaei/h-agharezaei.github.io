+++
date = '2027-04-01T10:00:00+03:30'
draft = false
title = 'gRPC over HTTP/2'
description = 'gRPC over HTTP/2 on loopback: the real headers and trailers, the 5-byte message prefix, grpc-timeout, status codes, one connection and GOAWAY.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "grpc", "http2", "protobuf", "go", "deadline"]
cover = { image = "/images/covers/net-grpc-over-http2.png", alt = "gRPC over HTTP/2", hiddenInSingle = true }
+++

In [the previous post](/posts/net-websocket/) we turned one connection into a message channel. {{< term "grpc" "gRPC" >}} takes the other road: it stays inside {{< term "http" "HTTP" >}}/2, as in [HTTP/2 and what changes](/posts/net-http2/), and adds a few rules on top. [A gRPC service in Go](/posts/go-grpc-service/) and [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) covered the API side; here I only look at the bytes.

> Everything ran on `127.0.0.1` with random ports (not printed), Go 1.26, macOS, grpc-go v1.84.0. The {{< term "protobuf" "protobuf" >}} code is the `orders` contract from the earlier post (copied), with a tiny new server. I did not run Linux, grpc-web or load balancing. The machine was busy, so counts, no timings.

## A raw HTTP/2 client

To see the wire I wrote a client that does not use grpc-go: it writes the HTTP/2 connection preface, sends a HEADERS frame and a DATA frame, and prints what comes back (`golang.org/x/net/http2` for the frames). One call, `GetOrder` with id `o1`:

```
request body bytes: 00 00 00 00 04 0a 02 6f 31
  HEADERS stream=1 end_stream=false
      :status: 200
      content-type: application/grpc
  DATA stream=1 end_stream=false len=23
      prefix=00 00 00 00 12 -> compressed=0 length=18
      message=0a026f31120361646118e209220470616964
    decoded: id="o1" customer="ada" cents=1250
  HEADERS stream=1 end_stream=true
      grpc-status: 0
      grpc-message: 
```

The request I sent was a POST to the path `/orders.v1.OrdersService/GetOrder` (package, service, method) with `content-type: application/grpc` and `te: trailers`. So a gRPC call is an ordinary HTTP/2 request. The response is headers, a DATA frame, and a final HEADERS frame with `end_stream=true`. That last block is {{< term "http-trailers" "trailers" >}}: the result of the call goes there because it is only known after the last message.

## The 5-byte prefix

Every message inside DATA starts with five bytes: one byte for the compression flag (0 means not compressed) and a 4-byte big-endian length. This is {{< term "message-framing" "message framing" >}} again: HTTP/2 DATA frames do not respect message boundaries, so gRPC adds its own length. In the request, `00 00 00 00 04` is followed by `0a 02 6f 31`: protobuf field 1, length 2, the text `o1`. The response length 0x12 = 18 matches the 23 DATA bytes minus the prefix.

## What the real client sends

Now the same call from the normal grpc-go client, with the server side recording the bytes it received and decoding them:

```
HEADERS stream=1 end_stream=false
    :method: POST
    :scheme: http
    :path: /orders.v1.OrdersService/GetOrder
    :authority: <addr>
    content-type: application/grpc
    user-agent: grpc-go/1.84.0
    te: trailers
    grpc-timeout: 1999472u
DATA stream=1 end_stream=true len=9
```

`:authority` is the address and port, which I replaced with `<addr>`. The client had a 2 second deadline and the header says `1999472u`: the remaining time in microseconds (`u`; `m` is milliseconds, `S` seconds). The {{< term "deadline" "deadline" >}} travels as a relative duration, so the server can cancel its work and pass the remainder on to the next call.

## Status codes

HTTP status is always 200. The real result is `grpc-status` in the trailers. A missing order was a **Trailers-Only** response, a single HEADERS frame with `end_stream=true` that holds both the HTTP part and the status:

```
HEADERS stream=1 end_stream=true
    :status: 200
    content-type: application/grpc
    grpc-status: 5
    grpc-message: order zzz not found
```

Real calls through the Go client, printing `codes.Code` names:

```
not found:         NotFound | "order zzz not found"
deadline:          DeadlineExceeded | "context deadline exceeded"
nothing listening: Unavailable
not implemented:   Unimplemented
```

The deadline case used 150 ms against a handler that waits 3 seconds. When I sent `grpc-timeout: 150m` from the raw client, no trailer came back, only `RST_STREAM stream=1 code=CANCEL`: this server cancelled the stream when time ran out, and the client library turns its own expired timer into `DeadlineExceeded`. `Unavailable` means no connection could be made.

## One connection, many calls

Over a single client connection: 50 sequential unary calls, one server stream of 5 messages, then 20 concurrent calls. The listener counted accepts and I decoded the client's HEADERS frames:

```
tcp connections accepted: 1
server-stream messages received: 5 (one RPC)
HTTP/2 streams opened: 71 (highest id 141)
```

One {{< term "tcp" "TCP" >}} connection, 71 RPCs, 71 streams. Client-initiated stream ids are odd and increase, hence 141. The server stream was one stream with five DATA frames, each with its own 5-byte prefix, and one trailer block at the end. This is {{< term "multiplexing" "multiplexing" >}}. HTTP/2 SETTINGS can limit concurrent streams per connection; I did not test grpc-go's defaults, so check the docs.

## GOAWAY on graceful stop

I started a server stream (5 messages, 150 ms apart), called `GracefulStop` in the middle and recorded the server's frames:

```
GOAWAY last_stream=2147483647 code=NO_ERROR
PING ack=false
PING ack=true
GOAWAY last_stream=1 code=NO_ERROR
DATA stream=1 ...   (messages 2 to 5)
HEADERS stream=1 end_stream=true
    grpc-status: 0
```

The server sends a first {{< term "goaway" "GOAWAY" >}} that does not limit anything, a PING round trip, then a second GOAWAY naming stream 1 as the last one it will handle. The running stream finished, all 5 messages arrived, and a new call afterwards returned `Unavailable`. It is the idea from [graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/).

## A few things to watch

- Always set a deadline on the client; without one a call can wait forever.
- Read the status from the trailers, not the HTTP status.
- A proxy in the middle must support HTTP/2 and trailers, or gRPC breaks.
- Retry `Unavailable` carefully, and only for idempotent calls.

## Exercise

Change the demo to send a 1 KiB message and look at the DATA frames. Does the prefix length equal the sum of the frame sizes?

## What's next

The next post is "Layer 4 and layer 7 load balancers".
