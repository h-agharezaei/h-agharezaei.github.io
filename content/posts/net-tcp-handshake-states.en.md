+++
date = '2027-01-12T10:00:00+03:30'
draft = false
title = 'TCP: the handshake and connection states'
description = 'The TCP handshake and connection states on loopback: LISTEN, ESTABLISHED, TIME_WAIT, half-close, RST, connection refused, timeouts and the listen backlog.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "handshake", "tcp-states", "python"]
cover = { image = "/images/covers/net-tcp-handshake-states.png", alt = "TCP: the handshake and connection states", hiddenInSingle = true }
+++

Two failures look similar from your code but feel completely different. In one, `connect()` fails at once with `connection refused`. In the other, it hangs for many seconds and then gives up with a timeout. A third symptom shows up on busy servers: thousands of sockets sitting in a state called `TIME_WAIT`. Each of these is a trace of what happens during the life of a {{< term "tcp" "TCP" >}} connection: it is opened, used and closed, and the kernel keeps track of where each connection is in that life.

The kernel's bookkeeping has names, called **states**, and you can look at them with ordinary tools. Knowing the states turns a vague "the network is flaky" into "these sockets are waiting for my program to close them" or "nobody is listening on that port". [DNS in practice](/posts/net-dns-in-practice/) turned a name into an address; here we connect to that address. If the packet and header vocabulary is new to you, [the TCP/IP model post](/posts/net-tcp-ip-model/) introduced it.

> Everything ran on macOS (arm64) with Python 3.14, on `127.0.0.1` with a random port (printed as `PORT`; the client's temporary port is `EPH`), or on the documentation address `192.0.2.1`. I have no root, so no packet capture. I show only the lines of my demo port: `netstat` also lists other connections of my machine, and those I do not publish.

## The three-way handshake

Before two programs can exchange data, they agree that both of them are ready. This is the {{< term "three-way-handshake" "three-way handshake" >}}, and it is much like a phone call: "Hello?", "Hello, can you hear me?", "Yes, I can." In TCP these are three segments:

1. The client sends **SYN** ("synchronize"): "I want to open a connection, and my first byte will be number 1000."
2. The server answers **SYN+ACK**: "OK, I heard you. My first byte will be number 5000."
3. The client answers **ACK** (acknowledgement): "I heard you too."

Both sides pick a starting number for their bytes, called the initial sequence number, and the other side confirms it. Every byte sent afterwards has a number, which is how TCP can detect lost data and put the bytes in order. The confirmation always carries the number of the *next* byte the sender expects, which is why the acknowledgement is the other side's number plus one: the SYN itself counts as one.

I cannot capture these segments on this machine, so `handshake_built.py` only builds the three headers by hand, with the same idea as in the earlier post. The numbers are invented and no real packet is sent:

```
client: 49152->80 seq=1000 ack=0 flags=SYN (0x02)
server: 80->49152 seq=5000 ack=1001 flags=SYN+ACK (0x12)
client: 49152->80 seq=1001 ack=5001 flags=ACK (0x10)
```

Read it top to bottom. The client (port 49152) starts with sequence 1000 and sets only the SYN flag. The server (port 80) replies with its own number 5000 and acknowledges `1001`, which is the client's 1000 plus one. The client closes the loop by acknowledging `5001`. The flag values `0x02`, `0x12` and `0x10` are SYN, SYN plus ACK, and ACK.

In your own code you never write any of this. The kernel does it: `connect()` returns after the handshake is finished, and on the other side `accept()` returns a connection that is already complete.

## States you can watch

A connection has a life, and the kernel names each stage of it. To watch it, `states.py` runs the following steps. At each step it pauses (a "checkpoint") so that I can run `netstat -an -p tcp` in another shell and look at the sockets:

1. The server calls `listen()`.
2. A client connects, and the server accepts.
3. The client calls `close()` first. The server then reads from its socket.
4. The server closes too.

(I ran `netstat` from the shell, because it printed nothing when I launched it from inside a Python subprocess in my setup.) Here are the lines of the demo port at each checkpoint:

```
== 1-listen
127.0.0.1.PORT    *.*                LISTEN
== 2-established
127.0.0.1.PORT    127.0.0.1.EPH    ESTABLISHED
127.0.0.1.EPH    127.0.0.1.PORT    ESTABLISHED
127.0.0.1.PORT    *.*                LISTEN
== 3-client-closed
127.0.0.1.PORT    127.0.0.1.EPH    CLOSE_WAIT
127.0.0.1.EPH    127.0.0.1.PORT    FIN_WAIT_2
127.0.0.1.PORT    *.*                LISTEN
== 4-both-closed
127.0.0.1.PORT    *.*                LISTEN
127.0.0.1.EPH    127.0.0.1.PORT    TIME_WAIT
server recv after client FIN: b''
```

The columns are local address, remote address and state. Let's go through the checkpoints:

- **`LISTEN`.** The server has a socket that accepts new connections. Its remote address is `*.*` because nobody is connected yet.
- **`ESTABLISHED`.** After the handshake, one connection shows up as two lines, because each side has its own socket: the server's end (local `PORT`, remote `EPH`) and the client's end (local `EPH`, remote `PORT`). The `LISTEN` socket is still there, ready for the next client.
- **`CLOSE_WAIT` and `FIN_WAIT_2`.** The client called `close()`, which sends a **FIN**, meaning "I will send nothing more". The server's kernel acknowledged it, so the client is in `FIN_WAIT_2` ("I closed, and I wait for the other side to close too"). The server's socket is in `CLOSE_WAIT`: it knows the peer is done and now waits for *my code* to call `close()`. The `b''` that `recv()` returned in the last line is the end-of-file the server's code sees at this moment.
- **`TIME_WAIT`.** The server closed as well and sent its own FIN. The side that closed first, the client, now sits in {{< term "time-wait" "TIME_WAIT" >}}, and the server's side is gone. The kernel keeps this entry for a while so that stray late packets of the old connection cannot be confused with a new one on the same ports. According to the docs, that wait is about twice the maximum segment lifetime; I did not wait for it to expire.

This gives a handy rule for debugging. Many sockets in `CLOSE_WAIT` mean your program receives the peer's close but never calls `close()`: that is a bug in your code. Many in `TIME_WAIT` are normal, and they sit on the side that closed first.

## Half-close

Closing is really two independent directions. You can tell the other side "I will not send more" and still keep reading. This is called a {{< term "half-close" "half-close" >}}, and in code it is `shutdown(SHUT_WR)`. It is useful when the end of your message must be marked by closing: the receiver reads until EOF, and then still has a way to send back the answer. `halfclose.py` shows this with a client and a server thread:

```
server: got b'hello' then EOF
client: after SHUT_WR, still reading -> b'reply sent after EOF: HELLO'
client: next recv -> b''
client: send after SHUT_WR -> BrokenPipeError [Errno 32] Broken pipe
```

The client sent `hello` and then closed its sending side. The server read until it saw EOF, then replied with the text in upper case. The client received that reply after its half-close, and then got `b''` once the server also closed. The last line shows the price: after `SHUT_WR` the client can no longer write, and trying fails with `BrokenPipeError`. In Go this is `CloseWrite()` on a `*net.TCPConn`; I did not run a Go version of this demo.

## Refused and timed out

Back to the two failures from the opening. `refused_timeout.py` provokes them. First it grabs a free port and closes the listener, so the port is free: nobody listens there. Then it tries to connect to it. After that, it connects to `192.0.2.1:80`, a documentation address that should not belong to anyone. Both attempts have a 2-second timeout:

```
loopback, closed port -> ConnectionRefusedError | [Errno 61] Connection refused
192.0.2.1:80 -> TimeoutError | timed out
```

On the closed port, the machine *is* there, so its kernel answers the SYN at once with an {{< term "tcp-rst" "RST" >}} (reset), a segment that means "no such connection, go away". Your program gets `refused` immediately. For `192.0.2.1` nothing answers at all. The SYN goes out and no reply ever comes back, so the client waits until its own timeout fires. As a rule of thumb: a **fast** failure usually means "wrong port: the host is up but nobody listens", and a **slow** one usually means "the host is unreachable, or a firewall silently drops packets". Both are only rules of thumb; some networks answer with an error message instead of silence.

## RST versus FIN

A FIN is an orderly goodbye. An RST is slamming the door. `rst.py` makes the server abort on purpose: it sets the option `SO_LINGER` with a timeout of zero before `close()`, which makes the kernel send an RST instead of a FIN:

```
client recv -> ConnectionResetError | [Errno 54] Connection reset by peer
```

Instead of a clean `b''`, the client gets an exception: `ECONNRESET`, "connection reset by peer". In real programs you typically see this when the peer aborts a connection, for example after a crash, or when a firewall or proxy kills it; I only reproduced the deliberate case here. Treat both EOF and `ECONNRESET` as normal network events that your code must handle.

## The listen backlog

The server's `listen(backlog)` call sets the size of a queue: connections that have finished the handshake but that the program has not yet taken with `accept()`. The {{< term "listen-backlog" "listen backlog" >}} matters when your accept loop is slower than the clients. According to the man page of `listen`, a client that arrives while the queue is full may get `ECONNREFUSED`, or the request may be ignored so that its retries can succeed. That depends on the system.

To see what macOS does, `backlog.py` listens with a backlog of 1, never calls `accept()`, and opens six clients, each with a 1.5-second timeout. It then tries to send one byte on each, and pauses at a checkpoint, where I ran `netstat -L` and `lsof`. The outcome of the connections is not always the same. This was the first run:

```
client 1: connect() returned
client 2: connect() returned
client 3: connect() returned
client 4: connect() returned
client 5: connect() returned
client 6: connect() returned
client 1: sendall ok
client 2: sendall -> BrokenPipeError | [Errno 32] Broken pipe
client 3: sendall -> BrokenPipeError | [Errno 32] Broken pipe
client 4: sendall -> BrokenPipeError | [Errno 32] Broken pipe
client 5: sendall -> BrokenPipeError | [Errno 32] Broken pipe
client 6: sendall -> BrokenPipeError | [Errno 32] Broken pipe
```

In the second run the `sendall` lines were identical, but the connect lines differed:

```
client 1: connect() returned
client 2: ConnectionResetError | [Errno 54] Connection reset by peer
client 3: ConnectionResetError | [Errno 54] Connection reset by peer
client 4: ConnectionResetError | [Errno 54] Connection reset by peer
client 5: ConnectionResetError | [Errno 54] Connection reset by peer
client 6: ConnectionResetError | [Errno 54] Connection reset by peer
```

(When I first ran this demo for the original version of this post, I saw only this second form, in three runs. Since both forms now appear, I read the difference as a timing race and cannot promise either.) What is stable is this: client 1 got the one place in the queue, and all the others were reset, so they either failed at `connect()` or at their first write. At the checkpoint, `netstat -L` showed `1/0/1` for the demo port: according to the man page, that is one unaccepted connection, no incomplete ones, and a maximum of one. `lsof` listed the other client sockets as `CLOSED`. I expect other systems to behave differently, for example by dropping the SYN so that clients wait and retry, but I could not run Linux here. The takeaway is system-independent: if your `accept()` loop falls behind, clients see errors or long waits.

## Idle connections and keepalive

A connection with no traffic stays `ESTABLISHED` forever, even if the other machine has vanished: there is nothing to tell you. {{< term "tcp-keepalive" "TCP keepalive" >}} makes the kernel send small probes on an idle connection, so that a dead peer is eventually noticed. `keepalive.py` only reads and sets the options; I did not wait for any probe:

```
SO_KEEPALIVE default: 0
SO_KEEPALIVE now:     8
idle seconds before the first probe (TCP_KEEPALIVE): 7200
after setting 30: 30
```

By default it is off (`0`). After enabling it, the value read back is `8`; that is just what macOS returns for "on" and I would not read anything into the number. The idle time before the first probe is 7200 seconds, two hours, on this macOS; the default differs per system, and `TCP_KEEPALIVE` is the macOS name of this option. After I set it to 30 seconds it reads back 30.

## Debugging by state

- Many `CLOSE_WAIT` sockets are your bug: the peer closed and your code never did. Many `TIME_WAIT` sockets are normal, and they sit on the side that closed first.
- Separate `refused` (fast, an RST came back) from a timeout (no answer at all) when you debug. They point at different problems.
- Always set connect and read timeouts. The defaults can be minutes, and a hung connection holds a thread or a goroutine.
- Treat `ECONNRESET` and EOF as normal network events, not as exceptional bugs.
- Backlog behaviour and keepalive defaults depend on the operating system; check yours instead of trusting numbers from a blog.

## Exercise

Change `states.py` so that the server closes first. Which side now shows `TIME_WAIT`? Then run `netstat` after the program exits and see how long the entry stays.

## What's next

The next post is "A TCP server and client from scratch". Now that we have watched the kernel's side of a connection, we write the code on both ends: accept loop, reading messages out of the stream, deadlines and a clean shutdown.
