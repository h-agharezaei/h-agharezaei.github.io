+++
date = '2027-01-22T10:00:00+03:30'
draft = false
title = 'A TCP server and client from scratch'
description = 'A TCP server in Go from scratch: Accept loop, byte-stream framing, a length-prefixed KV protocol, deadlines, half-close and clean shutdown.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "go", "framing", "protocol"]
cover = { image = "/images/covers/net-sockets-tcp-from-scratch.png", alt = "A TCP server and client from scratch", hiddenInSingle = true }
+++

In [the previous post](/posts/net-tcp-handshake-states/) we watched a connection open and close. Now we write both ends. The {{< term "socket" "socket" >}} API is small, but one fact about {{< term "tcp" "TCP" >}} bites everybody: it has no messages. We met this in [the TCP/IP model post](/posts/net-tcp-ip-model/); here we deal with it. The code uses `goroutine`s as in [goroutines and channels](/posts/go-goroutines-channels/).

> Everything ran on `127.0.0.1` with a random port (`:0`), Go 1.26, macOS. No addresses of my machine appear; ephemeral ports in one error line were replaced by `PORT`. The demo is a local example directory. The machine was busy, so I show no timings.

## Listen, accept, one goroutine per connection

```go
ln, _ := net.Listen("tcp", "127.0.0.1:0")
for {
    c, err := ln.Accept()
    if err != nil {
        if errors.Is(err, net.ErrClosed) { return nil } // listener closed: normal stop
        return err
    }
    go func() { defer c.Close(); handle(c) }()
}
```

`Accept` blocks until a client completes the handshake and returns a new socket for that client; the listening socket stays and keeps accepting.

## TCP is a byte stream

The client writes `hello\n` and `world\n` as two `Write` calls; the server sleeps 300 ms, so both have arrived, then reads. Later the client sends 10 bytes in one write and the server reads with a 4-byte buffer:

```
one Read: 12 bytes "hello\nworld\n"
Read(4):  4 bytes "0123"
Read(4):  4 bytes "4567"
Read(4):  2 bytes "89"
```

Two writes became one read, and one write became three reads. The sleep only makes the gluing reproducible; without it the result depends on timing. So a {{< term "stream" "stream" >}} needs {{< term "message-framing" "framing" >}}.

## Framing 1: newline-delimited

A tiny key-value protocol: `SET k v`, `GET k`, `QUIT`, one command per line. The server uses `bufio.Reader.ReadString('\n')` and a `sync.Mutex` around the map (see {{< term "mutex" "mutex" >}}). A real run:

```
> SET lang go  < OK
> GET lang     < VALUE go
> GET nope     < NOTFOUND
> QUIT         < BYE
```

Simple and readable with `nc`, but values cannot contain `\n`, and an endless line without a newline grows memory unless you cap it.

## Framing 2: length prefix

Each frame is a 4-byte big-endian length, then the payload. The reader uses `io.ReadFull`, which loops until the buffer is full:

```go
var hdr [4]byte
if _, err := io.ReadFull(r, hdr[:]); err != nil { return nil, err }
n := binary.BigEndian.Uint32(hdr[:])
if n > max { return nil, fmt.Errorf("%w: %d bytes (max %d)", ErrFrameTooLarge, n, max) }
p := make([]byte, n) // only after the guard
_, err := io.ReadFull(r, p)
```

The same three commands work and print the same replies. Two hostile clients show why the details matter. One announces 100 bytes, sends 5 and closes; the other claims about 2 GB:

```
server: read error: unexpected EOF
server: read error: frame too large: 2147483647 bytes (max 1048576)
```

`io.ErrUnexpectedEOF` means the stream ended in the middle of a frame (a plain `io.EOF` means it ended between frames, which is a clean close). The size check comes before `make`, so the liar costs us nothing.

## Deadlines and half-close

Without a time limit a silent client holds a goroutine forever. Before each read the server calls `SetReadDeadline(now + idle)`. With idle = 300 ms and a client that connects and says nothing:

```
server: read error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
client read after server gave up: EOF
```

A {{< term "deadline" "deadline" >}} is an absolute time, so it must be renewed per request. The other tool is a {{< term "half-close" "half-close" >}}: the client sends a body, calls `CloseWrite()`, and still reads the reply. The server's `io.ReadAll` returns only after that EOF:

```
server got 17 bytes, now replying
client got: counted 17 bytes
```

## Shutting down, and testing

`Shutdown` closes the listener (so `Accept` returns `net.ErrClosed`) and waits on a `sync.WaitGroup` for open connections; see [graceful shutdown](/posts/go-graceful-shutdown-workers/) and [sync, select and context](/posts/go-sync-select-context/). Output:

```
Serve returned: <nil>
dial after shutdown: refused=true
```

A `go test -race` test starts 20 clients, each doing 50 SET/GET pairs; it passed with the race detector on (`ok example.com/netkv`) and 1000 keys stored.

## The same in Python and Node

Python's `socket` module is a thin wrapper over the same calls: `bind`, `listen`, `accept`, `recv`, `sendall`. A 14-line echo server and client in one process printed `client got b'ping\n'`. Node has `net.createServer`, which fires a callback per connection (compare [node:http](/posts/node-http-server/)); I did not run a Node version here.

## A few things to watch

- Never assume one `Write` equals one `Read`; loop or use `io.ReadFull`.
- Cap every length you read from the network before allocating.
- Set deadlines on every connection you do not control.
- Check `net.ErrClosed` so a normal shutdown is not logged as an error.
- A mutex guards the map; run tests with `-race`.

## Exercise

Add a `DEL k` command to both modes. Then make the frame reader accept a client that sends the header one byte at a time (write it with a loop and sleeps) and show it still works.

## What's next

The next post is "UDP and how it differs from TCP".
