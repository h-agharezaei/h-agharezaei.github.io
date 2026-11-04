+++
date = '2027-01-22T10:00:00+03:30'
draft = false
title = 'A TCP server and client from scratch'
description = 'A TCP server in Go from scratch: Accept loop, byte-stream framing, a length-prefixed KV protocol, deadlines, half-close and clean shutdown.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "go", "framing", "protocol"]
cover = { image = "/images/covers/net-sockets-tcp-from-scratch.png", alt = "A TCP server and client from scratch", hiddenInSingle = true }
+++

Here is a fact that surprises almost everybody the first time. If one side calls `Write` twice, the other side may get everything in a single `Read`. And if one side calls `Write` once, the other side may need three `Read` calls to collect it. The reason is that {{< term "tcp" "TCP" >}} has no messages. It carries a stream of bytes, and the boundaries of your writes are not part of it.

The {{< term "socket" "socket" >}} API itself is small: listen, accept, read, write, close. The hard part is what you build on top of it, because you must decide yourself where one message ends and the next begins. In this post we write both ends of a TCP conversation in Go: a server that accepts many clients, and a tiny key-value protocol on top of it, first with one command per line and then with a length in front of every message. Along the way we deal with the things that break real servers: lying clients, silent clients, and shutting down cleanly.

[The previous post](/posts/net-tcp-handshake-states/) watched a connection open and close from the kernel's side, and [the TCP/IP model post](/posts/net-tcp-ip-model/) showed the stream. The code uses goroutines as in [goroutines and channels](/posts/go-goroutines-channels/).

> Everything ran on `127.0.0.1` with a random port (`:0`), Go 1.27.3, macOS. The demo was first written with Go 1.26. No addresses of my machine appear; ephemeral ports in one error line were replaced by `PORT`. The demo is a local example directory. I show no timings.

## Listen, accept, one goroutine per connection

A server does three things. It **listens** on an address, which tells the kernel "queue incoming connections for me". It **accepts** them one at a time: each `Accept` call waits until a client has finished the handshake and then returns a new socket for that client. And it handles each client, here in its own goroutine, so a slow client does not block the others:

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

The address `127.0.0.1:0` means "loopback, any free port"; the real port is available from `ln.Addr()`. The listening socket stays open and keeps accepting; each accepted socket `c` belongs to one client. `defer c.Close()` makes sure the connection is closed when the handler returns, however it returns. The special check for `net.ErrClosed` is for shutdown: when someone closes the listener, `Accept` fails with exactly that error, and that is a normal way to stop, not a failure to report.

## TCP is a byte stream

Before we design a protocol, let's see the problem. The `glue` mode of the demo has a server that accepts one connection, waits 300 milliseconds, and only then reads. The client writes `hello\n` and `world\n` as two separate `Write` calls. After that, the client sends `0123456789` in one write, and the server reads it with a buffer of only 4 bytes:

```
one Read: 12 bytes "hello\nworld\n"
Read(4):  4 bytes "0123"
Read(4):  4 bytes "4567"
Read(4):  2 bytes "89"
```

Two writes became one read of 12 bytes. And one write of 10 bytes was read in three pieces. The second effect is simply because I gave `Read` a 4-byte buffer, so it can return at most 4 bytes at a time; a smaller buffer is one way to see that a read is not tied to a write. The sleep in the server only makes the gluing reproducible: the two writes have both arrived by the time the first read happens. Without the sleep, the result depends on timing.

The conclusion is that TCP gives you bytes in order, and nothing else. A message boundary has to be part of the protocol you put on top, which is called {{< term "message-framing" "framing" >}}. There are two classic ways to do it, and we try both with the same tiny protocol.

## Framing 1: one command per line

The protocol has three commands: `SET key value`, `GET key` and `QUIT`. A command ends at a newline, `\n`. The server reads with `bufio.Reader.ReadString('\n')`, which keeps reading from the stream until it finds the delimiter, no matter how the bytes were cut up in transit. The map that holds the data is shared between all the connections, so a `sync.Mutex` (see {{< term "mutex" "mutex" >}}) protects it. In the `line` mode, one client sends four commands and prints the replies:

```
> SET lang go  < OK
> GET lang     < VALUE go
> GET nope     < NOTFOUND
> QUIT         < BYE
```

Each line shows the command sent (after `>`) and the reply (after `<`). `GET nope` asks for a key that was never set, and gets `NOTFOUND`. `QUIT` makes the server say `BYE` and close the connection.

This format is simple, and you can read it with your eyes. But it has two weak points. The value cannot contain a newline, since a newline is the end of the command. And if a client sends endless bytes without ever sending `\n`, the reader keeps collecting them in memory, so you must cap the line length in a real server.

## Framing 2: a length in front

The other way is to write the length before the data. In our frame format, each message is a 4-byte big-endian number (the length), followed by that many bytes of payload. For example, `SET lang go` is 11 bytes long, so its frame is the four bytes `00 00 00 0b` followed by the eleven bytes of text, 15 bytes in total. The reader first reads exactly 4 bytes, then exactly that many more:

```go
var hdr [4]byte
if _, err := io.ReadFull(r, hdr[:]); err != nil { return nil, err }
n := binary.BigEndian.Uint32(hdr[:])
if n > max { return nil, fmt.Errorf("%w: %d bytes (max %d)", ErrFrameTooLarge, n, max) }
p := make([]byte, n) // only after the guard
_, err := io.ReadFull(r, p)
```

`io.ReadFull` is the important function. A plain `Read` may return fewer bytes than the buffer holds, as we just saw. `ReadFull` keeps calling `Read` until the buffer is completely full or the stream ends. And the writer does the opposite with one `Write` that contains the header and the payload together (`WriteFrame` in the demo).

The `frame` mode runs the same commands and prints the same kind of replies:

```
> SET lang go  < OK
> GET lang     < VALUE go
> QUIT         < BYE
```

The format can carry any bytes, including newlines. But the length field comes from the network, so it is input from a stranger, and two hostile clients show why the details of the reader matter. The first announces a 100-byte frame, sends 5 bytes and closes. The second announces a frame of 2147483647 bytes, about 2 GB. These are the lines the server prints:

```
server: read error: unexpected EOF
server: read error: frame too large: 2147483647 bytes (max 1048576)
```

For the first client, `ReadFull` returns `io.ErrUnexpectedEOF`, which means "the stream ended in the middle of a frame". Compare it with a plain `io.EOF`, which means the stream ended *between* frames: that is a polite goodbye. For the second client, the size check refuses the frame (the limit is 1 MiB) before the program allocates anything. That ordering is the whole point: if we ran `make([]byte, n)` first, a single 4-byte message from a stranger could make the server ask for 2 GB of memory.

## Deadlines and half-close

A client that connects and then says nothing is a quiet way to hurt a server: without a time limit, its goroutine waits forever, and enough of them use up all your resources. The fix is a **deadline**. Before each read, the server calls `SetReadDeadline(now + idle)`. A {{< term "deadline" "deadline" >}} is an absolute point in time, not a duration, so it must be renewed before every request; otherwise it expires while the connection is perfectly healthy. In the `deadline` mode the server's idle limit is 300 ms and the client connects and stays silent for 600 ms:

```
server: read error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
client read after server gave up: EOF
```

The first line is the server giving up with an `i/o timeout` (the two ports in the real message are replaced by `PORT`). Its handler returns, `defer c.Close()` runs, and when the client finally reads, it sees `EOF`: the server closed the connection.

The other tool is the {{< term "half-close" "half-close" >}} from the previous post. Say the request has no length and no newline, and its end is marked by the client closing its sending side. In the `halfclose` mode, the client sends a body, calls `CloseWrite()`, and still reads the reply. The server uses `io.ReadAll`, which returns only after it sees that EOF:

```
server got 17 bytes, now replying
client got: counted 17 bytes
```

The body `some request body` has 17 bytes. The server counted them after the end-of-stream and answered over the same connection, which proves that the client's `CloseWrite()` closed one direction only.

## Shutting down cleanly, and testing

`Shutdown` first closes the listener, so `Accept` returns `net.ErrClosed` and the loop ends. Then it waits on a `sync.WaitGroup` until every open connection's handler has finished. For more on this pattern see [graceful shutdown](/posts/go-graceful-shutdown-workers/) and [sync, select and context](/posts/go-sync-select-context/). In the `shutdown` mode, a client does `QUIT`, the server shuts down, and the program then tries to connect again:

```
Serve returned: <nil>
dial after shutdown: refused=true
```

`Serve` returned `nil`, a normal stop, and a new connection is refused because nobody listens any more. That is the `connection refused` from the previous post, now caused by our own code.

A test starts 20 clients at once, and each does 50 `SET`/`GET` pairs on its own keys. I ran `go test -race` (the race detector watches for unsynchronised access to shared memory), and it passed; the test also checks that exactly 1000 keys end up in the map. I did not try removing the mutex, so I cannot show you the failure; the test is there to make that kind of mistake visible.

## The same in Python

Python's `socket` module is a thin wrapper over the same calls: `bind`, `listen`, `accept`, `recv`, `sendall`. A short echo server and client in one process (`echo.py`) printed `client got b'ping\n'`. Node has `net.createServer`, which fires a callback for each connection (compare [node:http](/posts/node-http-server/)); I did not run a Node version here.

## Hardening checklist

- **Never assume one `Write` equals one `Read`.** Loop until you have what you need, or use `io.ReadFull`.
- **Cap every length you read from the network before you allocate.** The size check in `ReadFrame` is what stands between a 4-byte message and a 2 GB allocation. The same goes for line length in a text protocol.
- **Set deadlines on every connection you do not control.** One silent client costs one goroutine and a socket; thousands of them cost the server.
- **Check `net.ErrClosed`** so that a normal shutdown is not logged as an error.
- **Guard shared state and run tests with `-race`.** One goroutine per connection means the map is touched concurrently from the first day.

## Exercise

Add a `DEL k` command to both modes. Then make the frame reader accept a client that sends the 4-byte header one byte at a time (write it with a loop and short sleeps) and show that it still works. Which function in the reader makes that possible?

## What's next

The next post is "UDP and how it differs from TCP". UDP is a protocol that keeps message boundaries, so the framing work in this post disappears, but so do the guarantees TCP gave us here: delivery, ordering and a connection.
