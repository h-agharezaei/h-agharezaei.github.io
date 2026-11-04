+++
date = '2027-04-01T10:00:00+03:30'
draft = false
title = 'gRPC over HTTP/2'
description = 'gRPC over HTTP/2 on loopback: the real headers and trailers, the 5-byte message prefix, grpc-timeout, status codes, one connection and GOAWAY.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "grpc", "http2", "protobuf", "go", "deadline"]
cover = { image = "/images/covers/net-grpc-over-http2.png", alt = "gRPC over HTTP/2", hiddenInSingle = true }
+++

Imagine your {{< term "grpc" "gRPC" >}} client says `NotFound`, but the access log of the proxy in front of the server says the same call returned {{< term "http" "HTTP" >}} status 200. Both are telling the truth. A gRPC call always travels as a successful HTTP request, even when the order you asked for does not exist, and the real result is written somewhere else: at the very end of the response, in a place called the trailers. If you do not know where to look, a gRPC failure looks like a success.

The idea behind gRPC is small. A gRPC call is an ordinary HTTP/2 request with a few agreed rules on top: the method name goes in the URL, every message gets a 5-byte length in front of it, the result comes after the last message, and the time limit travels in a header. There is no other channel. Once you have seen these four rules as bytes, errors like the one above stop being mysterious.

The earlier posts covered the API side: [A gRPC service in Go](/posts/go-grpc-service/) built a service, and [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) connected two languages. This post looks at what those libraries actually put on the wire. It builds on [HTTP/2 and what changes](/posts/net-http2/), where we saw that HTTP/2 splits a connection into many numbered streams. [The WebSocket post](/posts/net-websocket/) was about a protocol that leaves HTTP behind after the upgrade; gRPC is the opposite and stays inside HTTP/2 the whole time.

> Everything ran on `127.0.0.1` with random ports (not printed), macOS (Darwin arm64), Go 1.27.3 and grpc-go v1.84.0. The demo was first written with Go 1.26, and I re-ran it with 1.27.3 for this version. The {{< term "protobuf" "protobuf" >}} code is the `orders` contract from the earlier post (copied), with a tiny new server. I did not run Linux, grpc-web or a load balancer here. Values that change from run to run, such as the remaining time in a deadline header, will differ if you run it yourself.

## A few HTTP/2 words first

Four words from the HTTP/2 post are enough for everything below. A **connection** is the one {{< term "tcp" "TCP" >}} connection between client and server. A **stream** is one request and its response; each stream has a number, and many streams share the connection at the same time. A **frame** is the unit of bytes on the connection; every frame says which stream it belongs to. Two kinds of frame matter for us: a `HEADERS` frame carries header fields (name and value pairs, like `content-type`), and a `DATA` frame carries body bytes. The flag `end_stream=true` on a frame means "I will send nothing more on this stream".

## A gRPC call without a gRPC library

To see the bytes, I wrote a client that does not use grpc-go. It writes the HTTP/2 connection preface, sends one `HEADERS` frame and one `DATA` frame by hand, and prints every frame that comes back. It uses `golang.org/x/net/http2` only to read and write frames. The call is `GetOrder` with the id `o1`, an order that exists:

```
request body bytes: 00 00 00 00 04 0a 02 6f 31
  PING ack=false
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

The first line is the body I sent; I explain it in the next section. Everything indented is a frame the server sent back, in order.

- `PING` is a small frame that the other side must answer. HTTP/2 uses it to measure the round trip and to check that an idle connection is alive. It is not part of the call, and I did not look into why the server sent one here.
- The first `HEADERS` frame has `:status: 200` and `content-type: application/grpc`. This is the "everything is fine so far" part. It has `end_stream=false`, so more is coming.
- The `DATA` frame holds the answer: 23 bytes. The program decodes it as an order: id `o1`, customer `ada`, 1250 cents.
- The last `HEADERS` frame has `end_stream=true` and carries `grpc-status: 0`, which means OK. This block is the {{< term "http-trailers" "trailers" >}}: header fields sent after the body. The status is there because a server often does not know whether the call succeeded until it has sent the last message.

What I sent was a `POST` to the path `/orders.v1.OrdersService/GetOrder`. That path is the protobuf package, the service name and the method name, joined with slashes. I also sent `content-type: application/grpc` and `te: trailers`, which tells the server that this client can read trailers. So a gRPC call really is just an HTTP/2 request. Only the rules about the body and the trailers are new.

## The 5-byte prefix

Look at the first line of the output again. The body I sent was nine bytes: `00 00 00 00 04 0a 02 6f 31`. The last four, `0a 02 6f 31`, are the protobuf encoding of the request: field number 1, length 2, then the two characters `o1` (hex `6f 31`). The five bytes in front of them are the gRPC prefix.

The prefix has two parts: one byte that says whether the message is compressed (0 means no), and then a 4-byte length in big-endian order (here `00 00 00 04`, so the message is 4 bytes long). The response has the same shape: `00 00 00 00 12` means "not compressed, 18 bytes follow", and 5 + 18 is exactly the 23 bytes of the `DATA` frame.

Why does gRPC need this? It is the same problem as in [the TCP sockets post](/posts/net-sockets-tcp-from-scratch/): a byte stream has no message boundaries, and HTTP/2 `DATA` frames do not respect message boundaries either. A frame can hold half a message, or three messages. The prefix is gRPC's own {{< term "message-framing" "message framing" >}}: read five bytes, learn the length, read that many bytes, and you have one whole message.

You can check the response by hand. The 18 bytes `0a026f31 1203616461 18e209 220470616964` are four protobuf fields: field 1 is `o1`, field 2 is `ada`, field 3 is the number 1250 written as a varint (`e2 09`), and field 4 is the text `paid`.

## What the real client sends

Now the same call from the normal grpc-go client. The listener in my demo records every byte it receives, and the program decodes those bytes into frames afterwards. This is what the server side saw:

```
client -> server:
  HEADERS stream=1 end_stream=false
      :method: POST
      :scheme: http
      :path: /orders.v1.OrdersService/GetOrder
      :authority: <addr>
      content-type: application/grpc
      user-agent: grpc-go/1.84.0
      te: trailers
      grpc-timeout: 1998863u
  DATA stream=1 end_stream=true len=9
      prefix=00 00 00 00 04 -> compressed=0 length=4
      message=0a026f31
  PING ack=true
  PING ack=false
```

The headers are what I sent by hand, plus `user-agent`. `:authority` is the server address, which the demo replaces with `<addr>` before printing. The `DATA` frame is the same nine bytes, and it carries `end_stream=true` because a unary call (one request, one response) sends exactly one message. The two `PING` lines at the end are the client's answer to the server's ping (`ack=true`) and a ping of its own (`ack=false`).

The interesting line is `grpc-timeout: 1998863u`. The client had set a 2 second {{< term "deadline" "deadline" >}} on the call. The header does not hold a clock time; it holds the time that is left, here 1,998,863 microseconds (`u` means microseconds, `m` milliseconds and `S` seconds). The number changes on every run. Sending the remaining time, not a time of day, means the two machines do not need synchronized clocks. The server can cancel its work when the time is up, and it can pass whatever is left to the next service it calls.

## Status codes: the HTTP status says nothing

The real result of a call is `grpc-status` in the trailers. For an order that does not exist, the server did not even need to send a body. It answered with a single `HEADERS` frame that carries both the HTTP part and the gRPC status, and ends the stream. gRPC calls this a Trailers-Only response:

```
== not found:
request body bytes: 00 00 00 00 05 0a 03 7a 7a 7a
  PING ack=false
  HEADERS stream=1 end_stream=true
      :status: 200
      content-type: application/grpc
      grpc-status: 5
      grpc-message: order zzz not found
```

This is the answer to the opening puzzle. The HTTP status is 200 and the call failed with `grpc-status: 5`, which is `NotFound`. A proxy that only looks at `:status` counts this as a success. Anything that wants to know whether a gRPC call worked has to read `grpc-status`.

Here are four different failures seen from the normal Go client, printing the name of the code it received:

```
not found:         NotFound | "order zzz not found"
deadline:          DeadlineExceeded | "context deadline exceeded"
nothing listening: Unavailable
not implemented:   Unimplemented
```

- **NotFound** is the case above, sent by the server in `grpc-status` and `grpc-message`.
- **DeadlineExceeded** comes from a 150 ms deadline on a handler that waits 3 seconds. I also sent `grpc-timeout: 150m` from the raw client. No trailers came back. Only `RST_STREAM stream=1 code=CANCEL` arrived, which means the server cancelled the stream when the time ran out. My reading of this is that the Go client produced `DeadlineExceeded` from its own expired timer, not from a message of the server; I did not trace the client library to confirm it.
- **Unavailable** was the call to an address where nothing listens. No connection could be made, so no HTTP/2 frame was ever exchanged. The code was created inside the client. A proxy that fails in front of a gRPC server can cause the same code: according to the gRPC HTTP/2 protocol document, a client turns some HTTP statuses (for example 503) into `Unavailable`. I did not run that case.
- **Unimplemented** is what the server returns for a method it does not have. In my demo `CreateOrder` is declared in the contract but the server does not implement it.

## One connection, many calls

HTTP/2 lets many streams share a connection, and gRPC uses that fully. I made one client connection and did three things on it: 50 unary calls one after the other, one server-streaming call that returns 5 messages, and 20 calls at the same time. The listener counted accepted connections, and I decoded the `HEADERS` frames the client sent:

```
tcp connections accepted: 1
server-stream messages received: 5 (one RPC)
HTTP/2 streams opened: 71 (highest id 141)
```

That is 50 + 1 + 20 = 71 calls on one TCP connection, and 71 streams. A client chooses odd stream numbers and counts upward, so 71 streams end at id 141. The server-streaming call was a single stream with five `DATA` frames, each with its own 5-byte prefix, and one block of trailers at the end. This is {{< term "multiplexing" "multiplexing" >}}.

This is good for efficiency, because no call pays for a new TCP connection. It has a side effect that the next post is about: a device that balances load by connection sees one connection and cannot spread these 71 calls. HTTP/2 also lets the server limit how many streams can be open at the same time on one connection. I did not test what grpc-go does by default, so check its documentation if it matters to you.

## GOAWAY: stopping a server without cutting calls

What happens to a call that is half finished when the server wants to shut down? To see it, I started the server-streaming call (5 messages, 150 ms apart), called `GracefulStop` on the server in the middle of it, and recorded every frame the server sent. The client printed:

```
stream ended: EOF after 5 messages
new call after stop: Unavailable
```

All five messages arrived, and a new call afterwards was refused with `Unavailable`. The server-side frames show how:

```
server -> client:
  PING ack=false
  HEADERS stream=1 end_stream=false
      :status: 200
      content-type: application/grpc
  DATA stream=1 end_stream=false len=16
      prefix=00 00 00 00 0b -> compressed=0 length=11
      message=0a026f3112036164611864
  GOAWAY last_stream=2147483647 code=NO_ERROR
  PING ack=false
  PING ack=true
  GOAWAY last_stream=1 code=NO_ERROR
  DATA stream=1 end_stream=false len=17
      prefix=00 00 00 00 0c -> compressed=0 length=12
      message=0a026f32120361646118c801
  PING ack=true
  DATA stream=1 end_stream=false len=17
      ...   (messages 3, 4 and 5, each followed by a PING ack)
  HEADERS stream=1 end_stream=true
      grpc-status: 0
      grpc-message:
```

The output of my program has the same pattern for every message; I shortened messages 3 to 5 here. Read it from the top. The stream starts and message 1 is sent. In this run the shutdown began right after that, with a first {{< term "goaway" "GOAWAY" >}} frame. Its `last_stream=2147483647` is the largest possible stream number, so it does not exclude any stream yet. It only means "I am going to stop". Then the server sends a `PING` (its answer travels the other way, so it is not in this recording; the `PING ack=true` lines are the server answering the client's pings), and a second `GOAWAY` follows with `last_stream=1`: "stream 1 is the last one I will handle". RFC 9113 describes shutting down in these two steps: the first warning gives the client time to learn about it, so a call it started while the warning was still on its way is not lost. Stream 1 then finished normally with `grpc-status: 0`. It is the same idea as in [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/), with the protocol's own vocabulary.

## Where gRPC calls go wrong

- **No deadline on the client.** Without one, nothing ever tells the client to give up, and a call to a stuck server can wait forever. The deadline is also what the server uses to stop working on a call nobody is waiting for.
- **Reading the HTTP status.** As the not-found example showed, the HTTP status is almost always 200. Monitoring, retries and proxy rules that look at it will miss real failures. Look at `grpc-status`.
- **A proxy that does not speak HTTP/2 or does not pass trailers.** The status lives in the trailers. A middle box that drops or rewrites them makes every call look broken or successful for the wrong reasons.
- **Retrying everything that returns `Unavailable`.** It is often safe to retry, but only for idempotent calls, where repeating the request does no extra harm. Retrying "create an order" can create two orders.

## Exercise

Change the demo to send a request message larger than 16 KiB (16,384 bytes is the default maximum frame size in HTTP/2) and decode the `DATA` frames. How many frames does one message use, and does the length in the 5-byte prefix match the sum of the frame sizes? I did not run this one.

## What's next

The next post is "Layer 4 and layer 7 load balancers". Seventy-one calls on one connection raise a direct question: what can a load balancer do if it only sees connections, and what changes when it understands requests?
