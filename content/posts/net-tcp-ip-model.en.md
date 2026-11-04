+++
date = '2026-12-19T10:00:00+03:30'
draft = false
title = 'The TCP/IP model and the path of a packet'
description = 'The TCP/IP model with real code: build IPv4 and TCP headers by hand, verify the checksum, then watch one loopback connection and a TCP byte stream.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp-ip", "tcp", "ip", "sockets", "http"]
cover = { image = "/images/covers/net-tcp-ip-model.png", alt = "The TCP/IP model and the path of a packet", hiddenInSingle = true }
+++

Every service I wrote in this blog, like the [net/http API](/posts/go-http-api-stdlib/) or the [gRPC service](/posts/go-grpc-service/), ends in one call: "send these bytes to that address". It looks like one step. Underneath, several pieces of software hand the bytes to each other, and each one adds its own small label before passing them on.

You only notice this when something fails. `no such host`, `connection refused` and a plain timeout look like three versions of "the network is broken", but they come from three different places. Once you know which piece is responsible for what, the error message starts telling you where to look. This post is the map: the layers, what each one is for, and what one HTTP request looks like after every layer has added its label.

Since this is the first post of the networking series, I will not assume you have ever looked at a packet. We will build one by hand, then watch a real connection on your own machine.

> Everything ran on macOS (arm64) with Python 3.14, `curl` 8.7.1, `nc` and `lsof`. I have no root here, so there is no packet capture: instead we build the headers by hand and watch sockets. All addresses are loopback (`127.0.0.1`) or documentation examples (`192.0.2.10`, `198.51.100.20`), and the demo servers use a random local port.

## Four layers, one question each

Think of posting a parcel. You write a letter, put it in an envelope with the receiver's name, and the post office puts that envelope in a bag with a city label. A courier takes the bag to the next sorting centre. Nobody in the chain opens what is inside; each one only reads its own label.

Network software works the same way. It is split into layers, and each layer answers one question. The standard description, the {{< term "tcp-ip-model" "TCP/IP model" >}}, has four of them:

- **Link** answers: "how do I get these bytes to the machine next to me?" It covers one hop on one network, for example over Ethernet or Wi-Fi.
- **Internet** answers: "how do I get them to that machine anywhere in the world?" This is the job of IP: it gives every machine an address, and routers pass the packet from hop to hop.
- **Transport** answers: "which program on that machine, and did everything arrive?" This is {{< term "tcp" "TCP" >}} or UDP. They add port numbers, and TCP also adds reliability: it resends what was lost and delivers bytes in order.
- **Application** answers: "what do the bytes mean?" HTTP, DNS and gRPC live here. Your own code is at this layer.

You will also hear about the seven-layer **OSI** model. It cuts the same stack into thinner slices. The internet actually runs on TCP/IP, but OSI gave us a handy vocabulary: when someone says "a layer 4 load balancer" or "layer 7", they are counting OSI layers (4 is transport, 7 is application).

Now the errors make more sense. `no such host` usually means the name could not be turned into an address (DNS, an application-level protocol). `connection refused` means the machine was reached, but nothing listens on that port (transport). A timeout often means the packets are getting lost somewhere on the way (internet or link). We will see the first two of these in a real run in the post about the TCP handshake.

Going down the stack, each layer wraps what it received from the layer above. This is called {{< term "encapsulation" "encapsulation" >}}, like the letter in the envelope in the bag:

```
[ Ethernet header | [ IP header | [ TCP header | [ HTTP request ] ] ] ]
   link               internet      transport      application
```

The label each layer adds is called a **header**: a small block of bytes at the front, in a fixed format, so the receiver knows where each field starts. Let's build two of them ourselves.

## Building the headers by hand

An IPv4 header is 20 bytes (without options) and a TCP header is 20 bytes too. Python's `struct` module can pack numbers into exact byte layouts. The `!` in the format string means "network byte order": numbers are written with the most significant byte first (big-endian), which is what all internet headers use.

`headers.py` builds one packet carrying a small HTTP request, `GET / HTTP/1.1` with a `Host` header, 37 bytes in total. The packet goes from `192.0.2.10`, port 49152, to `198.51.100.20`, port 80. Then it prints every field and parses the packet back. These are the two lines that pack the headers (the rest of the script is bookkeeping):

```python
ip_hdr = struct.pack("!BBHHHBBH4s4s", (4 << 4) | 5, 0, total, 0x1234, 0x4000,
                     64, 6, csum, src, dst)
tcp_hdr = struct.pack("!HHIIBBHHH", 49152, 80, 1000, 5000, 5 << 4, 0x18, 64240, tcp_csum, 0)
```

This is the complete output:

```
IPv4 header:
  version+IHL      45
  DSCP/ECN         00
  total length     004d
  identification   1234
  flags+fragment   4000
  TTL              40
  protocol         06
  header checksum  3c25
  source           c000020a
  destination      c6336414
IPv4 header checksum field: 0x3c25
sum of header words incl. checksum: 0xffff
TCP header:
  src port         c000
  dst port         0050
  sequence         000003e8
  ack              00001388
  offset+flags     5018
  window           faf0
  checksum         a7fe
  urgent           0000
total bytes: 77 = 20 + 20 + 37
parsed: 192.0.2.10 -> 198.51.100.20 proto 6 ttl 64 len 77
parsed: port 49152 -> 80 PSH+ACK set: True window 64240
payload: GET / HTTP/1.1
```

All values are hexadecimal, so let's decode the ones that matter:

- `45` is two numbers in one byte: version `4` (IPv4) and a header length of `5` words. A word is 4 bytes, so 5 words is 20 bytes.
- `004d` is 77, the total length of the packet. That matches the line `total bytes: 77 = 20 + 20 + 37`: 20 bytes of IP header, 20 of TCP header and 37 of payload.
- `40` is 64: the **TTL** (time to live). Each router that forwards the packet subtracts one, and when it reaches zero the packet is dropped. This stops a packet from circling forever if the routing is wrong.
- `06` is the protocol of the layer above. Number 6 means TCP.
- `c000020a` is the source address. Four bytes: `c0`=192, `00`=0, `02`=2, `0a`=10, which is `192.0.2.10`. The destination `c6336414` is 198.51.100.20 in the same way.
- In the TCP header, `c000` is port 49152 and `0050` is port 80. `000003e8` is the sequence number 1000, and `00001388` is the acknowledgement number 5000. We will see in a later post what these two are for; here they are just numbers I invented.
- `5018` is again two things: `5` is the header length in words (20 bytes) and `18` holds the flags. `0x18` is PSH plus ACK, which the last line of the output confirms. `faf0` is 64240, the window: how many bytes the sender is willing to receive.

The fields I skipped (`DSCP/ECN`, `identification`, `flags+fragment`, `urgent`) are not needed for the rest of the series. The values here are just what I put in; `0x4000` happens to be the "don't fragment" flag.

### The checksum

Headers can get damaged in transit, so each protocol carries a {{< term "checksum" "checksum" >}}: a small number computed from the data, which lets the receiver notice accidental corruption. The IPv4 checksum is simple. Take the header as 16-bit words, add them up, fold any carry above 16 bits back into the sum, and flip all the bits:

```python
def checksum(data: bytes) -> int:
    if len(data) % 2: data += b"\0"
    s = sum(struct.unpack(f"!{len(data)//2}H", data))
    while s >> 16: s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF
```

The sender computes it with the checksum field set to zero and stores the result in that field. The receiver adds all ten words, this time including the checksum. If nothing changed, the sum is `0xffff`, and that is what the two lines in the output show: the field is `0x3c25`, and the sum of the whole header is `0xffff`.

Notice that a router lowers the TTL on every hop, so it has to compute this value again each time. The TCP checksum works the same way, but it also covers the payload and a "pseudo-header" with the two addresses (`a7fe` above). I computed it with the same function, but I did not compare it with a real network stack, so treat it as an illustration of the format.

The checksum catches accidents, not attackers: anyone can compute a correct one. Protection against attackers comes from TLS, which is a later topic in this series.

One more honest note: these bytes were built by my script and sent nowhere. They show the format of a packet, not what my machine really transmitted.

## Loopback and the MTU

For a real connection we need two programs that can talk without leaving the machine. Every computer has a virtual network interface for this, called {{< term "loopback" "loopback" >}}, with the address `127.0.0.1`. Packets sent to it never reach a cable or a Wi-Fi card; the operating system hands them straight back. It is perfect for experiments, and it is the only interface I show in this series. The first lines of `ifconfig lo0` (I printed only this interface, on purpose) look like this:

```
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	options=1203<RXCSUM,TXCSUM,TXSTATUS,SW_TIMESTAMP>
	inet 127.0.0.1 netmask 0xff000000
```

The interesting part is `mtu 16384`. The {{< term "mtu" "MTU" >}} (maximum transmission unit) is the largest packet one link can carry. According to the docs, classic Ethernet has an MTU of 1500 bytes; loopback here allows 16384. A larger packet would have to be cut into pieces or dropped. TCP avoids that by cutting its own data into segments that fit. With a 1500-byte MTU, one segment carries at most 1500 - 20 (IP header) - 20 (TCP header) = 1460 bytes of data, called the {{< term "mss" "MSS" >}} (maximum segment size). Option fields make the headers longer than 20 bytes and the MSS correspondingly smaller.

## A real connection

Now a real one. `server.py` starts a tiny HTTP server on `127.0.0.1` and a random free port, and prints that port (`PORT` below). First, `curl -v` shows the application layer: HTTP is just text. Lines starting with `>` are what `curl` sent, `<` is what came back, and `*` is curl's own commentary.

```
* Trying 127.0.0.1:PORT...
* Connected to 127.0.0.1 (127.0.0.1) port PORT
> GET / HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
> 
* Request completely sent off
* HTTP 1.0, assume close after body
< HTTP/1.0 200 OK
< Server: BaseHTTP/0.6 Python/3.14.0
< Date: Wed, 04 Nov 2026 16:30:01 GMT
< Content-Length: 33
< 
{ [33 bytes data]
* Closing connection
hello from the application layer
```

The request is the same `GET / HTTP/1.1` we put in our hand-made packet. Everything else, the connection, the headers below this text, is done by the layers underneath without `curl` writing a line about it. (The server speaks HTTP/1.0, which is why curl says it will assume the connection closes after the body.)

Next, I keep a connection open with `nc` (netcat, a small tool that opens a TCP connection and connects it to your keyboard) and ask which sockets exist. A {{< term "socket" "socket" >}} is what a program holds to talk over the network: one end of a connection. `lsof -nP -iTCP:PORT` lists them. I cut some columns, and replaced the server port with `PORT` and the client's temporary port with `EPH`:

```
python3.1  3u  IPv4  TCP 127.0.0.1:PORT (LISTEN)
python3.1  4u  IPv4  TCP 127.0.0.1:PORT->127.0.0.1:EPH (ESTABLISHED)
nc         3u  IPv4  TCP 127.0.0.1:EPH->127.0.0.1:PORT (ESTABLISHED)
```

There are three sockets. The first belongs to the server and is only listening: it waits for new connections. The second is the server's end of one accepted connection. The third is `nc`'s end of the same connection, which is why the two addresses are written in opposite order. A TCP connection is identified by four values together: source address, source port, destination address and destination port. `EPH` is a temporary ("ephemeral") port that the operating system chose for the client. That is why you never need to pick a port when you connect somewhere. And when the handshake finishes, `nc -v` prints `Connection to 127.0.0.1 port PORT [tcp/*] succeeded!`, which is the moment TCP has a connection ready. We will look at that handshake closely in a later post.

## TCP is a stream of bytes, not messages

There is one property of TCP that surprises almost everyone, and it drives much of how protocols are designed. `stream.py` opens a connection on loopback. The sender writes 10,000 bytes ten times, then closes. The receiver calls `recv()` in a loop and prints the size of each piece it gets:

```python
for _ in range(10): c.sendall(b"x" * 10_000)   # ten separate 10 KB writes
```

I ran it twice. The output differs, but the total never does:

```
sent: 10 writes of 10000 bytes = 100000
recv() sizes: [26332, 3668, 16332, 3668, 32664, 16332, 1004] total 100000
sent: 10 writes of 10000 bytes = 100000
recv() sizes: [65536, 34464] total 100000
```

The sender made ten writes of 10,000 bytes. The receiver saw seven pieces in the first run and two in the second, none of them 10,000 bytes. All 100,000 bytes arrived, in order, but the boundaries of my writes are gone. TCP gives you a stream, like a pipe, not a list of messages. How the bytes are cut depends on timing, buffer sizes and the operating system, so it changes from run to run.

This is why every protocol on top of TCP has its own way to say where a message ends. HTTP has the `Content-Length` header (and chunked encoding for bodies of unknown size), and gRPC puts the length in front of every message. Later in the series we write such a protocol ourselves.

## Common mistakes about layers

- **Mixing up "layer 4" and "layer 7".** A layer 7 load balancer reads the HTTP request and can route by path or header. A layer 4 one only sees IP addresses and ports, so it can only route connections.
- **Assuming one `Write` is one `Read`.** As the last demo showed, it is not. Always define where your messages start and end.
- **Trusting the checksum for security.** It detects accidental damage only. An attacker can send a perfectly valid checksum.
- **Forgetting that headers grow.** Options make the IP and TCP headers longer than 20 bytes, so the MSS is a little smaller than 1460.
- **Reading the hand-built bytes as real traffic.** They show the format; I did not capture real packets here.

## Exercise

Change `headers.py` to add a TCP option: MSS, which has kind 2, length 4 and value 1460. Set the data offset in the TCP header to 6 words, because the header is now 24 bytes, and make the parser read the option back. Then flip one bit in the IP header and show that the sum is no longer `0xffff`.

## What's next

The next post is "IP addressing and subnets". We saw `192.0.2.10` as four bytes in a header, but not how addresses are grouped into networks, which is what decides whether two machines can talk directly or need a router.
