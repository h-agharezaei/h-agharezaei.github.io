+++
date = '2027-02-15T10:00:00+03:30'
draft = false
title = 'HTTP/1.1 by hand'
description = 'HTTP/1.1 by hand on loopback: raw requests, the mandatory Host header, Content-Length vs chunked, persistent connections and a 50-line server.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http", "http1", "sockets", "go", "chunked"]
cover = { image = "/images/covers/net-http1-by-hand.png", alt = "HTTP/1.1 by hand", hiddenInSingle = true }
+++

Open a terminal and type this, with no browser and no HTTP library:

```
printf 'GET /hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' | nc 127.0.0.1 <port>
```

A web server on the other end answers with a few lines of plain text, and the last line is the page. That is all {{< term "http" "HTTP" >}}/1.1 is: text that two programs agree to write to each other over a {{< term "tcp" "TCP" >}} connection. If you only know HTTP through libraries (see [Building an API with net/http in Go](/posts/go-http-api-stdlib/) and [An HTTP server with node:http](/posts/node-http-server/)), this post shows you what they send and receive underneath.

There is one real problem to solve here. TCP gives us a stream of bytes with no boundaries, so where does one message end and the next begin? [Our TCP server](/posts/net-sockets-tcp-from-scratch/) invented its own framing, and [UDP](/posts/net-udp-sockets/) avoided the question because each datagram is one message. HTTP/1.1 answers it with headers that say how long the body is. We will speak it with raw bytes and no HTTP library on the client side.

> Everything ran on `127.0.0.1` with random ports, with Go 1.27.3, Python 3.14, `nc` and curl 8.7.1 on macOS (Darwin, arm64); the original run used Go 1.26. The target was a Go `net/http` server, and the client was a Python raw socket (and `nc`). Ports, the `Date` header and similar values change on every run. I did not run Linux, and the machine was busy, so there are no timings. The demo is a local example directory.

## The shape of a request

A request is a few lines of text. Here it is as Python bytes, as the demo sends it:

```python
b"GET /hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
```

Every line ends with CRLF, the two characters `\r\n` (carriage return, line feed). Reading it line by line:

- `GET /hello HTTP/1.1` is the **request line**: the method (what to do), the target (what to do it to) and the protocol version.
- `Host: localhost` and `Connection: close` are **headers**, one `Name: value` per line. `Connection: close` asks the server to close the connection after answering. Without it the server keeps the connection open for the next request, which we will use later.
- An empty line ends the headers. Whatever follows is the body, and a GET has none.

The reply from the Go server, with the CRLFs shown at the line ends (the `Date` is from the moment I ran it and changes every time):

```
HTTP/1.1 200 OK\r\n
Date: Wed, 04 Nov 2026 16:48:45 GMT\r\n
Content-Length: 6\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
hello\n
```

The first line is the **status line**: the version, a status code (`200`) and a short reason. After it come the headers and an empty line, and then the body, `hello\n`. The header `Content-Length: 6` is the answer to our framing problem. It says the body is exactly six bytes (`hello` and a newline), so the reader knows where the message ends without any delimiter. Piping the same request through `nc` returns exactly the same bytes, because HTTP is just text over a {{< term "socket" "socket" >}}.

## Host is mandatory

The `Host` header names the site you want. It exists so that one IP address can serve many sites: the server looks at it to decide which one you mean. According to RFC 9112, an HTTP/1.1 request without it is an error, and the Go server enforces this. This is what it answered when I left it out:

```
HTTP/1.1 400 Bad Request: missing required Host header\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
400 Bad Request: missing required Host header
```

A `400` means "your request is malformed", and the server closed the connection after it.

## A body, and HEAD

For a request with a body, the same idea applies in the other direction. For a POST I sent `Content-Length: 10` and ten bytes (`name=roham`). The handler replied `got 10 bytes: name=roham`, and the server log confirmed `body=10 bytes`. The header tells the receiver how many bytes to read before the message is complete. It is the length-prefix idea from {{< term "message-framing" "message framing" >}}, with the length written in a header instead of in front of the bytes.

A `HEAD` request asks for the same thing as a GET but without the body. The server returned the same headers, including `Content-Length: 6`, and then nothing. The length describes what a GET would have returned, and since a HEAD response never has a body, the client must not wait for those six bytes.

## Chunked: framing without a length

What if the server does not know the size when it starts to answer, for example when it streams data as it produces it? Then it cannot write `Content-Length`. HTTP/1.1 has a second way to frame the body: `Transfer-Encoding: chunked`. The body is sent in pieces, and each piece is preceded by its size in hexadecimal. A piece of size 0 ends the body.

In the demo the handler writes `alpha`, `bravo-bravo` and `c`, flushing after each, so each becomes its own chunk. My Python client decodes it by hand: it reads a size line, then that many bytes, then the CRLF after them, until the size is 0. This is its full output, headers included:

```
b'HTTP/1.1 200 OK\r\n'
b'Date: Wed, 04 Nov 2026 16:48:45 GMT\r\n'
b'Content-Type: text/plain; charset=utf-8\r\n'
b'Connection: close\r\n'
b'Transfer-Encoding: chunked\r\n'
size line b'5\r\n' -> 5
  data b'alpha'
size line b'b\r\n' -> 11
  data b'bravo-bravo'
size line b'1\r\n' -> 1
  data b'c'
size line b'0\r\n' -> 0
  data b''
```

Notice that there is no `Content-Length` among the headers. Each `size line` is the raw line the server sent, and the number after `->` is what the client made of it. `b` is 11 in hexadecimal, which is the length of `bravo-bravo`. The last chunk has size 0, and that is how the client knows the body is over. This is {{< term "chunked-encoding" "chunked encoding" >}}.

## One connection, many requests

Opening a TCP connection costs a handshake, so HTTP/1.1 connections are {{< term "keep-alive" "persistent" >}} by default: after a response, the same connection can carry the next request. To see it, the demo sends three requests on one socket, and only the third carries `Connection: close`:

```
client local port 57354
b'HTTP/1.1 200 OK' [] b'hello\n'
b'HTTP/1.1 200 OK' [] b'hello\n'
b'HTTP/1.1 200 OK' [b'Connection: close'] b'hello\n'
after close, recv -> b''
```

The first line is the client's own port. Each following line is one response: the status, the `Connection` header if there was one (the empty `[]` means none), and the body. The first two responses have no `Connection` header, which means the server is keeping the connection open. The third, which asked for it, comes back with `Connection: close`, and after it the server closes. Then `recv` returns `b''`, the end of the stream.

The server's own log shows that all three requests came from the same client port:

```
server: GET /hello from client port 57354
server: GET /hello from client port 57354
server: GET /hello from client port 57354
```

The one-shot requests from before each used a new connection, so each logged a different port (57349, 57351 and 57352 in this run). The ports differ from run to run. The same port three times is the proof that one connection carried three requests.

This is why a client reading a persistent connection must read exactly one message, using `Content-Length` or the chunks to know where it ends, and not "until the end of the stream". The stream does not end.

## A 50-line server

So far Go's `net/http` did the serving. How much is needed to be a server ourselves? Only a listener, a loop that reads lines until the blank line, and a reply with a correct `Content-Length`:

```go
line, _ := br.ReadString('\n')          // request line
for {                                    // headers
    h, _ := br.ReadString('\n')
    if strings.TrimRight(h, "\r\n") == "" { break }
}
fmt.Fprintf(c, "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"+
    "Content-Length: %d\r\n\r\n%s", len(body), body)
```

The full file (error handling, a goroutine per connection, `Connection: close` support) is 53 lines. I started it on a random port (shown as `PORT` below) and ran `curl -v --http1.1` against it. The lines starting with `>` are what curl sent, and the lines starting with `<` are what our server answered:

```
> GET /path?x=1 HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
>
< HTTP/1.1 200 OK
< Content-Type: text/plain
< Content-Length: 13
<
hi from tiny
```

curl, a real HTTP client, accepted our 53 lines as a server. The server also logged the same request line and three headers it received (`Host`, `User-Agent`, `Accept`), which matches the `>` lines. It works, but it ignores request bodies, chunked requests, header size limits, timeouts, pipelining and many other edge cases. That is why you use `net/http` in production.

## Why parsers must agree

One concept is worth knowing even though I do not demonstrate it. A request can say its length in two ways: `Content-Length` and `Transfer-Encoding: chunked`. If a proxy in front of a server and the server behind it disagree about which one decides where the request ends, then a few bytes can be read as the end of the first request by one of them and as the start of a second request by the other. That is {{< term "request-smuggling" "request smuggling" >}}. It belongs to the security series.

## Where hand-written HTTP breaks

- Lines end with CRLF and the headers end with an empty line. Accepting a bare `\n` may seem friendly, but it is exactly the kind of difference that makes two parsers disagree.
- A body needs `Content-Length` or chunked framing. Without one of them the receiver cannot know where the body ends, and has to wait for the connection to close.
- `Host` is required. Expect a 400 without it.
- On a persistent connection, read exactly one message, not "until EOF". The stream does not end between requests.
- Prefer a real HTTP library for anything beyond learning. The edge cases listed above are where a hand-written parser goes wrong.

## Exercise

Extend the tiny server to read `Content-Length` and echo the body back. Then send a body shorter than the header claims and see what your server does while it waits. What would a read deadline change?

## What's next

The next post is "TLS and certificates with openssl". Every byte above crossed the socket as plain text, so anyone on the path could read it. TLS is what protects it.
