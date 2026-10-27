+++
date = '2027-01-12T10:00:00+03:30'
draft = false
title = 'TCP: the handshake and connection states'
description = 'The TCP handshake and connection states on loopback: LISTEN, ESTABLISHED, TIME_WAIT, half-close, RST, connection refused, timeouts and the listen backlog.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "handshake", "tcp-states", "python"]
cover = { image = "/images/covers/net-tcp-handshake-states.png", alt = "TCP: the handshake and connection states", hiddenInSingle = true }
+++

In the previous post, [DNS in practice](/posts/net-dns-in-practice/), we turned a name into an address. Now we connect to it. A {{< term "tcp" "TCP" >}} connection has a life: it is opened, it is used, it is closed, and each phase leaves a visible state in the kernel. If you have ever seen `connection refused`, a timeout, or thousands of sockets stuck in `TIME_WAIT`, this post explains what they mean. It builds on [the TCP/IP model](/posts/net-tcp-ip-model/).

> Everything ran on macOS (arm64) with Python 3.14, on `127.0.0.1` with a random port (printed as `PORT`; the client's temporary port is `EPH`), or on the documentation address `192.0.2.1`. I have no root, so no packet capture. I show only the lines of my demo port.

## The three-way handshake

The {{< term "three-way-handshake" "three-way handshake" >}} opens a connection with three segments: the client sends **SYN**, the server answers **SYN+ACK**, the client sends **ACK**. Each side picks an initial sequence number and the other acknowledges it plus one. I cannot capture these on this machine, so this script only builds the three headers by hand, the same idea as in the earlier post (invented sequence numbers, no real packet):

```
client: 49152->80 seq=1000 ack=0 flags=SYN (0x02)
server: 80->49152 seq=5000 ack=1001 flags=SYN+ACK (0x12)
client: 49152->80 seq=1001 ack=5001 flags=ACK (0x10)
```

In real code the kernel does this: `connect()` returns after the handshake finished.

## States you can watch

The server calls `listen()`, a client connects, the client closes first. At each step the script pauses and I run `netstat -an -p tcp` in another shell (it printed nothing when launched from inside Python in my setup, so I ran it from the shell):

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

One connection has two sockets, one per side. After the client's `close()` (it sent FIN, the server acknowledged it) the server is in `CLOSE_WAIT`: it knows the peer is done, and waits for **my code** to close. The client is in `FIN_WAIT_2`. A pile of `CLOSE_WAIT` sockets means your program forgets to call `close()`. The `b''` from `recv` is the EOF.

After the server closed too, the side that closed first, the client, is in {{< term "time-wait" "TIME_WAIT" >}}. According to the docs it stays there about 2*MSL (twice the maximum segment lifetime) so stray packets die out; I did not wait.

## Half-close

Closing is two independent directions. `shutdown(SHUT_WR)` ({{< term "half-close" "half-close" >}}) says "I will not send more" while the socket can still read:

```
server: got b'hello' then EOF
client: after SHUT_WR, still reading -> b'reply sent after EOF: HELLO'
client: next recv -> b''
client: send after SHUT_WR -> BrokenPipeError [Errno 32] Broken pipe
```

In Go this is `CloseWrite()` on a `*net.TCPConn`; I did not run a Go version here.

## Refused and timed out

Two very different failures:

```
loopback, closed port -> ConnectionRefusedError | [Errno 61] Connection refused
192.0.2.1:80 -> TimeoutError | timed out
```

On a closed port the kernel answers the SYN at once with {{< term "tcp-rst" "RST" >}}, so you get a fast `refused`: the host is there, nobody listens. `192.0.2.1` is a documentation address, nothing answers, the SYN just gets no reply, and the client waits until my 2-second timeout. Fast failure usually means "wrong port", slow failure "unreachable host or a firewall dropping packets".

## RST versus FIN

FIN is an orderly close. RST aborts. Here the server sets `SO_LINGER` with a zero timeout before `close()`:

```
client recv -> ConnectionResetError | [Errno 54] Connection reset by peer
```

The client gets `ECONNRESET` instead of a clean EOF.

## The listen backlog

`listen(backlog)` sizes the queue of connections that finished the handshake but were not `accept()`ed. I listened with backlog 1, never called `accept()`, and opened six clients. The result is OS-specific; this is macOS, three identical runs:

```
client 1: connect() returned
client 2: ConnectionResetError | [Errno 54] Connection reset by peer
client 3: ConnectionResetError | [Errno 54] Connection reset by peer
...
```

`netstat -L` showed `1/0/1` (one queued connection) and `lsof` showed the other client sockets as `CLOSED`. I expect other systems to behave differently, for example by dropping the SYN so that clients wait and retry, but I could not run Linux here. A slow `accept()` loop becomes errors for clients.

## Idle connections and keepalive

A connection with no traffic stays ESTABLISHED forever, even if the peer's machine vanished. {{< term "tcp-keepalive" "TCP keepalive" >}} makes the kernel probe an idle connection. I only read and set the options (I did not wait for any probe):

```
SO_KEEPALIVE default: 0
SO_KEEPALIVE now:     8
idle seconds before the first probe (TCP_KEEPALIVE): 7200
after setting 30: 30
```

The `8` is just what macOS returns for "on"; the 7200-second default is the macOS value here and differs per system.

## A few things to watch

- Many `CLOSE_WAIT` sockets are your bug; many `TIME_WAIT` sockets are normal, and they sit on the side that closed first.
- Distinguish `refused` (fast, RST) from a timeout (no answer) when debugging.
- Always set connect and read timeouts; the default can be minutes.
- Treat `ECONNRESET` and EOF as normal network events.
- Backlog behaviour and keepalive defaults depend on the OS.

## Exercise

Change `states.py` so the server closes first. Which side now shows `TIME_WAIT`? Then read `netstat` after the program exits and see how long the entry stays.

## What's next

The next post is "A TCP server and client from scratch".
