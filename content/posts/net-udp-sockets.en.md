+++
date = '2027-02-03T10:00:00+03:30'
draft = false
title = 'UDP and how it differs from TCP'
description = 'UDP in Go on loopback: datagram boundaries, the size limit, ICMP errors, a lossy proxy and a stop-and-wait layer that makes it reliable.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "udp", "sockets", "go", "datagram", "reliability"]
cover = { image = "/images/covers/net-udp-sockets.png", alt = "UDP and how it differs from TCP", hiddenInSingle = true }
+++

In [the previous post](/posts/net-sockets-tcp-from-scratch/) we wrote a TCP server and learned that a stream has no messages. {{< term "udp" "UDP" >}} is the opposite: it has nothing but messages, and no promises. We met both in [the TCP/IP model post](/posts/net-tcp-ip-model/) and used UDP for DNS in [DNS in practice](/posts/net-dns-in-practice/). Here we poke at it on a {{< term "loopback" "loopback" >}} interface and then build the missing guarantees ourselves.

> Everything ran on `127.0.0.1` with random ports, Go 1.26, macOS. Ephemeral ports in error lines were replaced by `PORT`. I did not run Linux, and the machine was busy, so there are no timings. The demo is a local example directory.

## An echo server

```go
pc, _ := net.ListenPacket("udp", "127.0.0.1:0")
n, addr, _ := pc.ReadFrom(buf)   // who sent it?
pc.WriteTo(buf[:n], addr)        // reply to that address
```

There is no `Accept`: one {{< term "socket" "socket" >}} serves everybody, and every datagram carries its sender's address. The client printed `client got "ping"`. Python's version is the same shape with `sendto` and `recvfrom` and printed `client got b'ping'`.

## Boundaries are preserved

Remember the TCP result where two writes became one read. Here the client sends `hello\n` and `world\n` as two writes, the server waits until both are queued, then reads:

```
ReadFrom #1: 6 bytes "hello\n"
ReadFrom #2: 6 bytes "world\n"
ReadFrom(4): 4 bytes "0123"
next read: timeout (the other 6 bytes are gone)
```

Each {{< term "datagram" "datagram" >}} is one read, no {{< term "message-framing" "framing" >}} needed. The flip side is the last two lines: a 10-byte datagram read into a 4-byte buffer keeps 4 bytes and the rest is discarded. Size your buffer for the biggest datagram.

## How big can a datagram be?

According to the docs, an IPv4 UDP payload is at most 65,507 bytes. I sent growing sizes on this Mac:

```
  9000 bytes: write ok
  9216 bytes: write ok
  9217 bytes: write error: write: message too long
 65507 bytes: write error: write: message too long
```

The error appears at `Write`, before anything is sent, and it is far below 65,507. The macOS setting `net.inet.udp.maxdgram` was 9216 here, which matches. I did not test Linux, so do not copy this number. Real networks fragment or drop big datagrams anyway; staying under one {{< term "mtu" "MTU" >}} (about 1,200 to 1,400 bytes) is the safe habit.

## No connection, so who tells you about errors?

`net.Dial("udp", ...)` does not connect to anything; it only stores a default peer. With nothing listening on the port:

```
connected socket, Write error: <nil>
connected socket, next Read error: read udp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection refused
unconnected socket, WriteTo error: <nil>
unconnected socket, ReadFrom error: read udp 127.0.0.1:PORT: i/o timeout
```

The write always succeeds. The host answers with an {{< term "icmp" "ICMP" >}} port-unreachable message, and a connected socket reports it as `connection refused` on the next read. An unconnected socket never hears about it and just times out (see {{< term "deadline" "deadlines" >}}). That is the only error feedback UDP gives, and it is not guaranteed to arrive.

## Loss, duplication, reordering

Loopback almost never drops, so I wrote a small UDP proxy with a fixed pattern: drop datagrams 3 and 7, duplicate 1, and swap 4 and 5. The sender sends `m0`..`m9`:

```
sent:    m0 m1 m2 m3 m4 m5 m6 m7 m8 m9
receiver: m0 m1 m1 m2 m5 m4 m6 m8 m9
```

Two lost, one doubled, one pair swapped, and no error anywhere. The real internet does this occasionally, so a UDP application must expect it.

## Making it reliable: stop-and-wait

The smallest fix is {{< term "stop-and-wait" "stop-and-wait" >}}: prefix each message with a 4-byte sequence number, wait for an ACK carrying the same number, and resend after a timeout. The receiver delivers only the next expected number and ACKs everything it has seen, so duplicates are harmless. About 60 lines in total; the core of the sender:

```go
for tries := 0; ; tries++ {
    c.Write(pkt)
    c.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
    n, err := c.Read(buf)
    if err == nil && n == 4 && binary.BigEndian.Uint32(buf) == uint32(seq) { break }
}
```

The proxy now drops every third data datagram, duplicates the second and drops every fourth ACK. Two runs gave the same result:

```
sent 8 messages: 14 datagrams on the wire, 6 retransmits, 1 stale ACKs ignored
delivered in order: alpha bravo charlie delta echo foxtrot golf hotel
```

All eight arrived, in order, exactly once, at the price of 6 resends. Stop-and-wait sends one packet per round trip, so it is slow; real protocols keep many packets in flight. This is, in miniature, what {{< term "tcp" "TCP" >}} does for you.

## Why use UDP at all?

When you want your own rules. DNS fits a question and an answer in one datagram each, with no handshake. Real-time audio and video prefer a late packet dropped over a stale one delivered. QUIC, the transport under HTTP/3, builds its own reliability on top of UDP; I only mention it here and did not test it.

## A few things to watch

- One `Write` is one datagram, one `Read` is one datagram; use a big enough buffer.
- Success from `Write` says nothing about delivery.
- Keep payloads under the MTU.
- Always set read deadlines; silence is normal.
- Number your messages if order or duplicates matter.

## Exercise

Change the proxy pattern so it drops the first three copies of every packet, and find how many retransmits the sender needs. Then add a retry limit that returns an error instead of looping forever.

## What's next

The next post is "HTTP/1.1 by hand".
