+++
date = '2026-12-19T10:00:00+03:30'
draft = false
title = 'The TCP/IP model and the path of a packet'
description = 'The TCP/IP model with real code: build IPv4 and TCP headers by hand, verify the checksum, then watch one loopback connection and a TCP byte stream.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp-ip", "tcp", "ip", "sockets", "http"]
cover = { image = "/images/covers/net-tcp-ip-model.png", alt = "The TCP/IP model and the path of a packet", hiddenInSingle = true }
+++

Every service I wrote in this blog, like the [net/http API](/posts/go-http-api-stdlib/) or the [gRPC service](/posts/go-grpc-service/), ends with one call: "send these bytes to that address". This new series looks at what happens under that call. We start with the map: the layers, and how one HTTP request becomes a packet.

> Everything ran on macOS (arm64) with Python 3.14, `curl`, `nc` and `lsof`. I have no root here, so there is no packet capture; instead we build headers by hand and watch sockets. All addresses are loopback or documentation examples (`192.0.2.10`, `198.51.100.20`), and the demo uses a random local port.

## Four layers

The {{< term "tcp-ip-model" "TCP/IP model" >}} has four layers: **link** (one hop on one network, for example Ethernet or Wi-Fi), **internet** (IP: addresses and hop-by-hop routing), **transport** (TCP or UDP: ports, and for TCP reliability) and **application** (HTTP, DNS, gRPC). The 7-layer **OSI** model splits the same stack more finely. Both exist because OSI is a good teaching vocabulary ("layer 4", "layer 7"), while TCP/IP is what the internet actually implements.

Going down, each layer wraps the one above, which is called {{< term "encapsulation" "encapsulation" >}}:

```
[ Ethernet header | [ IP header | [ TCP header | [ HTTP request ] ] ] ]
   link               internet      transport      application
```

## Build the headers by hand

An IPv4 header is 20 bytes without options, a TCP header is 20 bytes. Python's `struct` can pack them (`!` means network byte order, big-endian). The script builds one packet carrying a small HTTP request from `192.0.2.10:49152` to `198.51.100.20:80`, then parses it back:

```python
ip_hdr = struct.pack("!BBHHHBBH4s4s", (4 << 4) | 5, 0, total, 0x1234, 0x4000,
                     64, 6, csum, src, dst)
tcp_hdr = struct.pack("!HHIIBBHHH", 49152, 80, 1000, 5000, 5 << 4, 0x18, 64240, tcp_csum, 0)
```

```
IPv4 header:
  version+IHL      45
  total length     004d
  TTL              40
  protocol         06
  header checksum  3c25
  source           c000020a
  destination      c6336414
TCP header:
  src port         c000
  dst port         0050
  sequence         000003e8
  offset+flags     5018
  window           faf0
total bytes: 77 = 20 + 20 + 37
parsed: 192.0.2.10 -> 198.51.100.20 proto 6 ttl 64 len 77
parsed: port 49152 -> 80 PSH+ACK set: True window 64240
```

(I trimmed some fields from the printout.) `45` means version 4 and a header of 5 words; `06` is the protocol number of TCP; `c000020a` is `192.0.2.10`. The {{< term "checksum" "checksum" >}} is the one's complement of the sum of the header's 16-bit words. To verify it, sum all ten words including the checksum field:

```
IPv4 header checksum field: 0x3c25
sum of header words incl. checksum: 0xffff
```

That `0xffff` is exactly what the algorithm promises for an intact header. A router also decrements the TTL on each hop, so it must recompute this value. The TCP checksum additionally covers a pseudo-header with the addresses; I computed it the same way, but I did not verify it against a real stack.

## Loopback and the MTU

`ifconfig lo0` reduced to the loopback lines (the real output also lists my other interfaces, which I removed):

```
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	inet 127.0.0.1 netmask 0xff000000
```

The loopback {{< term "mtu" "MTU" >}} is 16384 here. According to the docs, classic Ethernet has an MTU of 1500, so a TCP segment carries at most about 1460 bytes of data (the {{< term "mss" "MSS" >}}: 1500 minus 20 for IP and 20 for TCP). An IP packet bigger than the link MTU must be fragmented or dropped; TCP avoids this by choosing segments that fit.

## A real connection, and the application layer

I start a tiny HTTP server on `127.0.0.1` (random port, shown as `PORT`). `curl -v` shows the application layer, which is plain text:

```
> GET / HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
< HTTP/1.0 200 OK
< Content-Length: 33
hello from the application layer
```

While `nc` holds a connection open, `lsof -nP -iTCP:PORT` shows the {{< term "socket" "sockets" >}} (I cut columns and replaced the port):

```
python3.1  3u  IPv4  TCP 127.0.0.1:PORT (LISTEN)
python3.1  4u  IPv4  TCP 127.0.0.1:PORT->127.0.0.1:58632 (ESTABLISHED)
nc         3u  IPv4  TCP 127.0.0.1:58632->127.0.0.1:PORT (ESTABLISHED)
```

The server has one listening socket and one accepted socket; `nc` has the other end. The connection is identified by the four values source address, source port, destination address, destination port. `nc -v` also reports `Connection to 127.0.0.1 port PORT [tcp/*] succeeded!` when the {{< term "tcp" "TCP" >}} handshake completes.

## TCP is a stream

Let me send 100,000 bytes as ten separate 10,000-byte writes and see what the receiver gets from `recv()`. I ran it twice:

```
sent: 10 writes of 10000 bytes = 100000
recv() sizes: [26332, 20000, 3668, 32664, 17336] total 100000
recv() sizes: [65536, 4464, 30000] total 100000
```

The total always matches, but the chunk sizes do not follow my writes and change between runs. TCP delivers an ordered stream of bytes with no message boundaries. This is why HTTP has `Content-Length` and chunked encoding, and why gRPC adds a length prefix to every message.

## A few things to watch

- "Layer 7" and "layer 4" load balancers differ in which header they read: the first understands HTTP, the second only IP and ports.
- Never assume one `Write` equals one `Read`; always frame your messages.
- The checksum catches accidents, not attackers. Security comes from TLS, a later topic.
- Header sizes matter: with options, headers are longer than 20 bytes and the MSS gets smaller.
- I did not capture real packets here; the hand-built bytes show the format, not what my machine sent.

## Exercise

Change the script to add a TCP option (for example MSS, kind 2, length 4, value 1460), update the data offset in the TCP header to 6 words, and make the parser read it back. Then flip one bit in the IP header and show the sum is no longer `0xffff`.

## What's next

The next post is "IP addressing and subnets".
