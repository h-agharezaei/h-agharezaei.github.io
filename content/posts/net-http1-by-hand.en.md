+++
date = '2027-02-15T10:00:00+03:30'
draft = false
title = 'HTTP/1.1 by hand'
description = 'HTTP/1.1 by hand on loopback: raw requests, the mandatory Host header, Content-Length vs chunked, persistent connections and a 50-line server.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http", "http1", "sockets", "go", "chunked"]
cover = { image = "/images/covers/net-http1-by-hand.png", alt = "HTTP/1.1 by hand", hiddenInSingle = true }
+++

In [the previous post](/posts/net-udp-sockets/) we saw datagrams, and before that [a TCP server](/posts/net-sockets-tcp-from-scratch/) taught us that a stream has no message boundaries. {{< term "http" "HTTP" >}}/1.1 is one answer to "where does a message end?", built on top of {{< term "tcp" "TCP" >}}. Today we speak it with raw bytes, with no HTTP library on the client side. For the library view see [Building an API with net/http in Go](/posts/go-http-api-stdlib/) and [An HTTP server with node:http](/posts/node-http-server/).

> Everything ran on `127.0.0.1` with random ports, Go 1.26, Python 3.14, macOS. A `net/http` server was the target; the client was a Python raw socket (and `nc`). I did not run Linux, and the machine was busy, so there are no timings. The demo is a local example directory.

## The shape of a request

```python
b"GET /hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
```

A request line (method, target, version), header lines, and a blank line, each ended by CRLF (`\r\n`). The reply from the Go server (CRLFs shown at line ends):

```
HTTP/1.1 200 OK\r\n
Date: Tue, 27 Oct 2026 05:50:20 GMT\r\n
Content-Length: 6\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
hello\n
```

A status line, headers, a blank line, then the body. `nc` gets the same bytes, since HTTP is just text over a {{< term "socket" "socket" >}}.

## Host is mandatory

HTTP/1.1 requires `Host` so one IP can serve many sites. Without it, this server answered:

```
HTTP/1.1 400 Bad Request: missing required Host header\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
400 Bad Request: missing required Host header
```

## A body, and HEAD

For a POST I sent `Content-Length: 10` and ten bytes (`name=roham`). The handler replied `got 10 bytes: name=roham`, and the server log confirmed `body=10 bytes`. The length header tells the receiver how many bytes to read, which is the length-prefix idea from {{< term "message-framing" "message framing" >}}.

A `HEAD` request returned the same headers, including `Content-Length: 6`, but no body at all. The length describes what a GET would have returned.

## Chunked: framing without a length

When the size is unknown up front, the response uses `Transfer-Encoding: chunked`. The handler wrote `alpha`, `bravo-bravo` and `c`, flushing after each. My Python client decoded it by hand: hex size line, data, CRLF, until a size of 0:

```
Transfer-Encoding: chunked
size line b'5\r\n' -> 5       data b'alpha'
size line b'b\r\n' -> 11      data b'bravo-bravo'
size line b'1\r\n' -> 1       data b'c'
size line b'0\r\n' -> 0       data b''
```

`b` is 11 in hex. This is {{< term "chunked-encoding" "chunked encoding" >}}, and there is no `Content-Length` in that response.

## One connection, many requests

HTTP/1.1 connections are {{< term "keep-alive" "persistent" >}} by default. I sent three requests on one socket; the third carried `Connection: close`. The client's local port was 50429, and the server log shows the same client port three times:

```
server: GET /hello from client port 50429
server: GET /hello from client port 50429
server: GET /hello from client port 50429
```

The earlier one-shot requests each logged a different port (50424, 50426, 50427). After the third reply the server closed, and `recv` returned `b''`, the end of the stream.

## A 50-line server

The server needs a listener, a loop reading lines until the blank line, and a reply with a correct `Content-Length`:

```go
line, _ := br.ReadString('\n')          // request line
for {                                    // headers
    h, _ := br.ReadString('\n')
    if strings.TrimRight(h, "\r\n") == "" { break }
}
fmt.Fprintf(c, "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"+
    "Content-Length: %d\r\n\r\n%s", len(body), body)
```

The full file (error handling, a goroutine per connection, `Connection: close` support) is 53 lines. `curl -v --http1.1` against it printed:

```
> GET /path?x=1 HTTP/1.1
> Host: 127.0.0.1:50433
> User-Agent: curl/8.7.1
> Accept: */*
>
< HTTP/1.1 200 OK
< Content-Type: text/plain
< Content-Length: 13
<
hi from tiny
```

My server logged the same request line and three headers. It works, but it ignores request bodies, chunked requests, header size limits, timeouts, pipelining and many edge cases. That is why you use `net/http` in production.

## Why parsers must agree

One concept only: if a proxy and a backend disagree about whether `Content-Length` or `Transfer-Encoding` decides where a request ends, bytes can be read as the start of another request. That is {{< term "request-smuggling" "request smuggling" >}}. I did not demonstrate it; it belongs to the security series.

## A few things to watch

- Lines end with CRLF and headers end with a blank line; a bare `\n` is not safe to rely on.
- A body needs `Content-Length` or chunked framing, otherwise the receiver cannot know where it ends.
- `Host` is required; expect a 400 without it.
- Reading from a persistent connection means reading exactly one message, not "until EOF".
- Prefer a real HTTP library for anything beyond learning.

## Exercise

Extend the tiny server to read `Content-Length` and echo the body back. Then send a body shorter than the header claims and see what your server does while it waits. What would a read deadline change?

## What's next

The next post is "TLS and certificates with openssl".
