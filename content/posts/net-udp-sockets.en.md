+++
date = '2027-02-03T10:00:00+03:30'
draft = false
title = 'UDP and how it differs from TCP'
description = 'UDP in Go on loopback: datagram boundaries, the size limit, ICMP errors, a lossy proxy and a stop-and-wait layer that makes it reliable.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "udp", "sockets", "go", "datagram", "reliability"]
cover = { image = "/images/covers/net-udp-sockets.png", alt = "UDP and how it differs from TCP", hiddenInSingle = true }
+++

You send a message to another program, `Write` returns without an error, and nothing arrives. No exception, no log line, no reset. Somewhere between the two programs the message just disappeared, and nobody told you. With {{< term "tcp" "TCP" >}} a lost message is sent again, and a connection that is really dead ends in a timeout or a reset. With {{< term "udp" "UDP" >}} silent loss is normal behaviour.

The idea is easy to state. TCP gives you a reliable, ordered stream of bytes (the one from [the previous post](/posts/net-sockets-tcp-from-scratch/)). UDP gives you almost nothing on top of IP: it adds port numbers, so that a message reaches the right program on a machine, plus a length and a checksum. Each message is sent on its own, and that is all. There is no connection, no retransmission, no ordering and no promise of delivery. We met both protocols in [the TCP/IP model post](/posts/net-tcp-ip-model/), and UDP was already carrying the questions in [DNS in practice](/posts/net-dns-in-practice/).

In this post we poke at UDP on a {{< term "loopback" "loopback" >}} interface (the virtual network inside your own machine, `127.0.0.1`) to see what "just messages" means in code. Then we build the missing guarantees ourselves, in about 60 lines, to see what TCP is doing for us.

> Everything ran on `127.0.0.1` with random ports, with Go 1.27.3 on macOS (Darwin, arm64); the original run used Go 1.26. Ephemeral ports in error lines were replaced by `PORT`. I did not run Linux. Loopback is not a real network and the machine was busy, so I show no timings. The demo is a local example directory.

## An echo server

We start with the smallest possible program: a server that sends back whatever it receives.

```go
pc, _ := net.ListenPacket("udp", "127.0.0.1:0")
n, addr, _ := pc.ReadFrom(buf)   // who sent it?
pc.WriteTo(buf[:n], addr)        // reply to that address
```

`127.0.0.1:0` means "any free port on loopback". The first thing to notice is what is missing: there is no `Accept`. In TCP, the server has one listening {{< term "socket" "socket" >}} and one new socket per client. In UDP, one socket serves everybody, and every message arrives together with the address of whoever sent it. That is why `ReadFrom` returns an address and `WriteTo` takes one: it is the only way to answer.

The client sent `ping` and printed `client got "ping"`. The Python version is the same shape with `sendto` and `recvfrom`, and printed `client got b'ping'`.

## Boundaries are preserved

A TCP stream has no message boundaries: two writes can arrive as one read, or one write as two. UDP is the opposite. In the next demo the client sends `hello\n` and `world\n` as two separate writes. The server waits until both are queued and then reads. Afterwards the client sends ten bytes (`0123456789`), and the server reads them into a buffer of only four bytes:

```
ReadFrom #1: 6 bytes "hello\n"
ReadFrom #2: 6 bytes "world\n"
ReadFrom(4): 4 bytes "0123"
next read: timeout (the other 6 bytes are gone)
```

The first two lines show that each {{< term "datagram" "datagram" >}} (UDP's word for one message) comes out as exactly one read, in the same size it went in. We did not need any {{< term "message-framing" "framing" >}}, the length prefix or delimiter that TCP programs add to find message ends.

The last two lines show the price. The ten-byte datagram was read into a four-byte buffer: we got `0123`, and the other six bytes were thrown away. The next read waited and timed out, because there was nothing left. No error was reported for the truncation. So size your buffer for the largest datagram you expect.

## How big can a datagram be?

According to the docs, an IPv4 UDP payload can be at most 65,507 bytes. Let us see what this Mac accepts. The demo writes datagrams of growing size, then reads whatever arrives:

```
  1000 bytes: write ok
  9000 bytes: write ok
  9216 bytes: write ok
  9217 bytes: write error: write: message too long
 20000 bytes: write error: write: message too long
 65507 bytes: write error: write: message too long
 65508 bytes: write error: write: message too long
received a datagram of 1000 bytes
received a datagram of 9000 bytes
received a datagram of 9216 bytes
```

The error shows up at `Write`, before anything is sent, and it happens far below 65,507. On this machine the macOS setting `net.inet.udp.maxdgram` is 9216 (I checked with `sysctl`), which matches the last size that worked. The three datagrams that were written successfully all arrived. I did not test Linux, so do not copy this number as a general limit.

Even when the system accepts a large datagram, a real network may not carry it. Every link has a maximum packet size, the {{< term "mtu" "MTU" >}} (often 1,500 bytes on Ethernet). A bigger datagram is split into fragments, and if one fragment is lost the whole datagram is lost. The safe habit is to keep payloads under about 1,200 to 1,400 bytes.

## No connection, so who tells you about errors?

In TCP, `connect` fails with "connection refused" if nobody listens. UDP has no handshake, so what happens when you send to a port with nobody behind it? In Go, `net.Dial("udp", ...)` does not connect to anything: it only remembers a default peer so that you can use `Write` and `Read` instead of `WriteTo` and `ReadFrom`. The next demo sends to a loopback port that nobody listens on, first with such a "connected" socket and then with a normal one:

```
connected socket, Write error: <nil>
connected socket, next Read error: read udp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection refused
unconnected socket, WriteTo error: <nil>
unconnected socket, ReadFrom error: read udp 127.0.0.1:PORT: i/o timeout
```

The write succeeds in both cases: it only means the datagram left our program. The machine on the other side did notice that nobody listens, and it answers with an {{< term "icmp" "ICMP" >}} "port unreachable" message (ICMP is the control-message protocol of IP). A connected socket receives that message and reports it as `connection refused` on the next read, which is line 2. An unconnected socket gets no such report, so it waits until its {{< term "deadline" "deadline" >}} passes and fails with `i/o timeout`. That ICMP message is the only error feedback UDP ever gives you, and nothing guarantees that it arrives: a firewall, for example, may drop it.

## Loss, duplication, reordering

Now the failures themselves. Loopback almost never loses packets, so I wrote a small UDP proxy that sits between the sender and the receiver and misbehaves in a fixed pattern. It drops datagrams 3 and 7 (counting from 0), duplicates datagram 1, and holds datagram 4 back until 5 has gone, which swaps them. The sender sends `m0` to `m9`:

```
sent:    m0 m1 m2 m3 m4 m5 m6 m7 m8 m9
receiver: m0 m1 m1 m2 m5 m4 m6 m8 m9
```

Compare the two lines. `m3` and `m7` are missing, `m1` appears twice, and `m5` arrives before `m4`. Two lost, one doubled, one pair swapped, and no error anywhere. The real Internet does all of this from time to time, so a program that uses UDP must expect it.

## Making it reliable: stop-and-wait

What would we need to build on top, to get TCP's guarantees back? The simplest scheme is {{< term "stop-and-wait" "stop-and-wait" >}}:

1. The sender puts a 4-byte sequence number in front of each message and sends it.
2. It waits for an acknowledgement (ACK) that carries the same number. If none arrives within a timeout, it sends the same datagram again.
3. The receiver delivers a message only if it has the next expected number. It acknowledges every number it has already seen, so a duplicate does no harm: it is acknowledged again and ignored.

In Go the receiver side is a few lines, and the core of the sender is a loop:

```go
seq := binary.BigEndian.Uint32(buf[:4])
if seq == expect { // new data: deliver in order
    out = append(out, string(buf[4:n]))
    expect++
}
if seq < expect { // new or duplicate: always ACK it
    // send back the 4-byte seq
}
```

```go
for tries := 0; ; tries++ {
    c.Write(pkt)
    c.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
    n, err := c.Read(buf)
    if err == nil && n == 4 && binary.BigEndian.Uint32(buf) == uint32(seq) { break }
}
```

(The full version in the demo also counts datagrams and skips ACKs for older numbers; about 60 lines in total.) To test it, the same proxy now drops every third data datagram, duplicates the second, and drops every fourth ACK on the way back. The demo sends eight messages. I ran it twice here and got the same result both times, though the timeouts depend on timing, so a very loaded machine could give different counts:

```
sent 8 messages: 14 datagrams on the wire, 6 retransmits, 1 stale ACKs ignored
delivered in order: alpha bravo charlie delta echo foxtrot golf hotel
```

All eight messages arrived, in order, exactly once. The price was 6 extra datagrams: 8 first sends plus 6 resends is the 14 on the wire. The "stale ACK" comes from the duplicated datagram: the receiver acknowledged the same number twice, and the second ACK reached the sender while it was already waiting for a later one, so the sender ignored it.

This works, but it is slow, because only one datagram is in flight at a time and the sender idles for a full round trip after each one. Real protocols keep many datagrams in flight and adapt to the network. This is, in miniature, what {{< term "tcp" "TCP" >}} does for you.

## Why use UDP at all?

When you want your own rules, or when a late answer is worse than no answer. DNS fits one question and one answer in one datagram each, with no handshake to pay for. Real-time audio and video would rather drop a late packet than play a stale one. QUIC, the transport under HTTP/3, builds its own reliability and encryption on top of UDP. I only mention it here and did not test it.

## Habits for UDP code

- One `Write` is one datagram and one `Read` is one datagram. Give `Read` a buffer big enough for the largest datagram, or the rest is silently cut off.
- A successful `Write` says nothing about delivery. It only means the datagram left your program.
- Keep payloads under the MTU, around 1,200 to 1,400 bytes, so they are not fragmented.
- Always set read deadlines. In UDP, silence is a normal outcome, and without a deadline your program waits forever.
- Number your messages if order or duplicates matter to you, as we did above.

## Exercise

Change the proxy pattern so it drops the first three copies of every packet, and find how many retransmits the sender needs. Then add a retry limit that returns an error instead of looping forever.

## What's next

The next post is "HTTP/1.1 by hand". TCP gives us a stream with no message boundaries, and HTTP is one answer to that problem: it marks where a message ends with headers.
