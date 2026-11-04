+++
date = '2027-01-02T10:00:00+03:30'
draft = false
title = 'DNS in practice'
description = 'DNS in practice with real dig runs, a query built by hand with Python struct and a tiny authoritative server in Go: records, TTL, NXDOMAIN and delegation.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "dns", "dig", "udp", "go", "python"]
cover = { image = "/images/covers/net-dns-in-practice.png", alt = "DNS in practice", hiddenInSingle = true }
+++

Before your program can send a single packet to `example.com`, something has to answer a different question: which IP address is that? The answer comes from {{< term "dns" "DNS" >}}, the Domain Name System, and it is easy to forget because it works silently. When it does not, the symptoms are strange: a request that is slow before it even starts, a hostname that points somewhere you did not expect, or `no such host` for a name that works on another machine.

I will give you a taste of the strange part right away. In the run for this post I asked a public resolver for the address of `example.com` and got `172.66.147.243` and `104.20.23.154`. Later I asked the servers that actually own the name, and they answered `188.114.98.0` and `188.114.99.0`. Same name, same minute, different answers. By the end of the post you will know why that is not a bug in DNS, and which of these two questions your program actually asks.

[The previous post](/posts/net-addressing-subnets/) computed with addresses, and [the TCP/IP model post](/posts/net-tcp-ip-model/) showed the layers: DNS is an application-level protocol that usually rides on {{< term "udp" "UDP" >}}, a simpler sibling of TCP that sends independent messages without a connection. This time we read real answers with `dig`, build a query byte by byte, and write a tiny DNS server of our own.

> macOS (arm64), Go 1.27.3, Python 3.14, `dig` 9.10.6. Every `dig` and script that goes to the internet names the public resolver `1.1.1.1` explicitly, so the address of my own resolver never appears. Where I removed or replaced something I say so. The local demos use `127.0.0.1` and a random port. I did not measure any timings.

## What DNS is

DNS is a phone book that no single computer holds. It is split into many parts, run by different organisations, and arranged as a tree. At the top are the **root servers**, which know who is responsible for each top-level domain such as `com`. The `com` servers know who is responsible for each name under `com`, such as `example.com`. And the servers of `example.com` itself hold the real data: the records.

A **record** is one entry in this book. It has a name, a type and a value. The type says what kind of information it is: for example, an `A` record maps a name to an IPv4 address.

Your program does not walk this tree itself. It asks a helper called a **resolver**, which does the walking and remembers the results for a while (a cache). We will meet both sides, the resolver and the servers that own the data, in a moment.

## Reading records with dig

`dig` is the standard command-line tool for asking DNS questions. `example.com` is a name reserved for documentation (according to RFC 2606), so it is safe to query. I add `+noall +answer` so that only the answer section is printed. These are real answers from the public resolver `1.1.1.1`, one query per record type:

```
example.com.  191    IN  A      172.66.147.243
example.com.  191    IN  A      104.20.23.154
example.com.  142    IN  AAAA   2606:4700:10::6814:179a
example.com.  142    IN  AAAA   2606:4700:10::ac42:93f3
example.com.  80867  IN  NS     hera.ns.cloudflare.com.
example.com.  80867  IN  NS     elliott.ns.cloudflare.com.
example.com.  222    IN  MX     0 .
example.com.  17     IN  TXT    "v=spf1 -all"
example.com.  17     IN  TXT    "_k2n1y4vw3qtb4skdx9e7dxt97qrmmq9"
example.com.  850    IN  SOA    elliott.ns.cloudflare.com. dns.cloudflare.com. 2418004112 10000 2400 604800 1800
```

(I only re-aligned the columns; dig separates them with tabs.) Each line reads: name, remaining {{< term "ttl" "TTL" >}} in seconds (more on that below), class `IN` (the internet, the only class you will use), the record type, and the value. The types:

- `A` is an IPv4 address and `AAAA` is an IPv6 address. A name can have several, as here.
- `NS` names the servers that are responsible for the zone, that is, the part of the tree owned by `example.com`.
- `MX` says where mail for the domain goes. The value `0 .` means "this domain accepts no mail".
- `TXT` is free text. Here it carries an email policy (SPF) that says no server is allowed to send mail for this domain; the second line is another piece of text that I do not interpret.
- `SOA` (start of authority) describes the zone itself: its main server, a contact, a serial number and some timers.

## TTL and caching

The second column is the TTL. A cache may reuse a record for that many seconds before it has to ask again. It is the knob that trades freshness against load: a low TTL means changes spread fast but more lookups happen, a high one means the reverse.

To see the cache at work, I asked for the `A` record twice, six seconds apart:

```
example.com.  8    IN  A  172.66.147.243
example.com.  8    IN  A  104.20.23.154
...six seconds later...
example.com.  219  IN  A  172.66.147.243
example.com.  219  IN  A  104.20.23.154
```

If one cache answered both times, the second TTL would be smaller, about 2. It is much larger, which one cache could not produce. A big public resolver is not one machine but many, and each machine has its own cache, so two queries can reach caches that filled at different times. I did not dig further into how this resolver is built. A TTL that goes down tells you "this came from a cache", but you cannot rely on it going down smoothly.

## NXDOMAIN, and the NOERROR that fools you

What if the name does not exist? A resolver reports that in the `status` of the answer. I asked for `nonexistent-name.invalid` (the `.invalid` top-level domain is reserved so that it never exists):

```
$ dig @1.1.1.1 nonexistent-name.invalid A
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
```

{{< term "nxdomain" "NXDOMAIN" >}} means "this name does not exist". Now compare it with `nonexistent-name.example.com`, which I expected to fail the same way:

```
$ dig @1.1.1.1 nonexistent-name.example.com A
;; ->>HEADER<<- opcode: QUERY, status: NOERROR
;; flags: qr rd ra ad; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
;; AUTHORITY SECTION:
example.com.  1800  IN  SOA  elliott.ns.cloudflare.com. dns.cloudflare.com. 2418004112 10000 2400 604800 1800
```

That was a surprise: `NOERROR`, zero answers, and a `SOA` record in the authority section. In general, `NOERROR` with an empty answer means "the name exists, but it has no record of the type you asked". Here the name evidently does not exist as a normal host, yet the zone answers this way. I did not look into why the example zone behaves like this, so I will not guess. The lesson is practical: `NOERROR` is not the same as "found", so check that the answer section is not empty. Also, resolvers cache these negative answers too, for a time that comes from the `SOA` record.

## Who answers: recursive versus authoritative

Now back to the opening mystery. `1.1.1.1` is a {{< term "recursive-resolver" "recursive resolver" >}}: you ask it once, and it does all the walking for you and caches what it learns. The servers that hold the real data, like `hera.ns.cloudflare.com` for `example.com`, are the {{< term "authoritative-server" "authoritative servers" >}}.

`dig +trace` does the resolver's work itself, from the top, so we can watch it. I print only the names (not the signatures or the addresses of the servers I contacted), and each group is a step:

```
.             NS   a.root-servers.net. ... m.root-servers.net.        (13 root servers)
com.          NS   a.gtld-servers.net. ... m.gtld-servers.net.       (13 servers for com)
example.com.  NS   hera.ns.cloudflare.com. / elliott.ns.cloudflare.com.
example.com.  A    188.114.99.0 / 188.114.98.0
```

The path is: ask a root server, which points to the `com` servers. Ask one of those, which points to the name servers of `example.com`. Ask one of those, and it finally gives the `A` record. Each step is a **delegation**: "I do not know, but they do."

And here is the mystery solved, partly. The last line comes straight from an authoritative server, and it holds `188.114.98.0` and `188.114.99.0`. The recursive resolver earlier gave different addresses. So an authoritative server is allowed to give different answers to different askers, and the name servers of `example.com` belong to Cloudflare (the `NS` names say so), a company that serves websites from many places. I did not check how it picks its answers, so I will not claim more. The lesson is simply: what your program sees is what its resolver says, and that can differ from what another resolver, or the authoritative server, says.

## A query by hand

DNS messages are small and have a fixed layout, so we can build one ourselves. A message has a 12-byte header (an id, flags, and four counts) followed by the question: the name, a type and a class. The name is written as **labels**, each one preceded by its length, and ending with a zero byte. `example.com` becomes `\x07example\x03com\x00`. `rawdns.py` builds the query this way:

```python
header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)  # RD set
qname = b"\x07example\x03com\x00"
q = header + qname + struct.pack("!HH", 1, 1)               # A, IN
```

The id `0x1234` is just a number I chose, to match the reply to the question. `0x0100` sets one flag, RD ("recursion desired": please do the walking for me). The `1, 0, 0, 0` are the counts: one question, no answers or other records. The last line adds type 1 (`A`) and class 1 (`IN`). The script sends this to `1.1.1.1` port 53 over UDP, and then again over {{< term "tcp" "TCP" >}}, where DNS adds a 2-byte length in front of each message. Here is the output:

```
query: 29 bytes 123401000001000000000000076578616d706c6503636f6d0000010001
UDP reply 61 bytes
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 149 A 104.20.23.154
  name bytes: c00c example.com TTL 149 A 172.66.147.243
TCP reply 61 bytes (2-byte length prefix)
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 43 A 172.66.147.243
  name bytes: c00c example.com TTL 43 A 104.20.23.154
```

The query is 29 bytes: 12 for the header, 13 for the name (1+7+1+3+1) and 4 for type and class. You can find them in the hex: `1234 0100 0001 0000 0000 0000`, then `07 6578616d706c65` (`example`), `03 636f6d` (`com`), `00`, then `0001 0001`.

In the reply, `QR=1` marks a response, `RCODE=0` means no error, `RA=1` says recursion is available, and `ANCOUNT=2` counts the answers. The name in each answer is just `c00c`. The top two bits `11` mean "pointer", and the remaining 14 bits (`0x00C`, which is 12) point at offset 12 in the message, where the question's name already sits. This is name compression: the name is written once and pointed to afterwards. It also explains the 61 bytes: 12 + 17 for the question + 2 answers of 16 bytes each.

Notice that both transports gave the same kind of answer, but the order of the two addresses and the TTL changed between them. Those values vary from run to run.

## A tiny authoritative server

Now the other side. `toy/main.go` is a DNS server in under a hundred lines. It listens on a UDP port on `127.0.0.1` (the demo hard-codes 5300; I ran a scratch copy on another free port, shown as `PORT` below). Any name under `.test`, a top-level domain reserved for testing (RFC 6761), gets an `A` record with the value `127.0.0.1`; everything else gets NXDOMAIN. The heart of the server builds the reply from the request:

```go
flags := uint16(0x8400) | (binary.BigEndian.Uint16(req[2:]) & 0x0100) // QR, AA, copy RD
...
resp = append(resp, 0xC0, 0x0C, 0, 1, 0, 1, 0, 0, 0, 30, 0, 4, 127, 0, 0, 1)
```

`0x8400` sets two flags: QR (this is a response) and AA (authoritative answer). The long line is one answer record: the pointer `C00C` to the question's name, type 1, class 1, a TTL of 30, a length of 4 and the four bytes of `127.0.0.1`. Now I can ask it with the real `dig`:

```
$ dig @127.0.0.1 -p PORT shop.test
;; flags: qr aa rd; QUERY: 1, ANSWER: 1
;; WARNING: recursion requested but not available
shop.test.  30 IN A 127.0.0.1
$ dig @127.0.0.1 -p PORT api.shop.test +short
127.0.0.1
$ dig @127.0.0.1 -p PORT example.com
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
```

The flag `aa` is the authoritative-answer mark we put there. `dig` warns that recursion is not available, which is right: this server only answers for what it owns and does not walk the tree for anybody. Asking for `shop.test` with type `MX` (not in the transcript above; I tried it too) gives `status: NOERROR` with no answer: the same "empty NOERROR" we met earlier, this time made by our own code.

## The resolver inside your program

Your own programs ask the same way. Go's `net.Resolver` takes a custom `Dial` function, which lets us point it at our toy server with a few lines (the `lookup` mode of the demo):

```go
r := &net.Resolver{PreferGo: true, Dial: func(ctx context.Context, network, _ string) (net.Conn, error) {
    var d net.Dialer
    return d.DialContext(ctx, network, "127.0.0.1:PORT")
}}
addrs, err := r.LookupHost(context.Background(), name)
```

For `shop.test` and `missing.example.com` it printed:

```
shop.test [127.0.0.1] <nil>
missing.example.com [] lookup missing.example.com on <resolver>:53: no such host
```

The first resolved through our server. The second got NXDOMAIN, which Go reports as `no such host`; the real message also names the address of the system's configured resolver, which I replaced with `<resolver>`. In normal programs you do not talk to DNS like this. Python's `socket.getaddrinfo` and Go's `net.LookupHost` go through the operating system: in my run `localhost` gave `127.0.0.1` (and `::1` in Go), and `example.com` gave its public addresses. The OS consults `/etc/hosts` and the configured resolvers in an order set by the system configuration; I do not paste that configuration here because it names my network. Go can use its own pure-Go resolver or the C library's: with `GODEBUG=netdns=go` and `netdns=cgo` both resolved `localhost` and `example.com`, and that is all I claim.

## Common DNS traps

- **Slow requests that are really slow lookups.** A cache miss costs several round trips, and a failing resolver adds a timeout before the real request even starts. A later case-study post chases one down.
- **TTL is a trade.** A low TTL gives fast changes but more lookups; a high one the opposite. Changing a record does not take effect everywhere at once.
- **`NOERROR` with an empty answer is not NXDOMAIN.** The first means the name exists without that record type, and the zone may do the same for names that do not exist, as we saw.
- **Answers can be reordered or differ between askers.** Do not depend on the first address, and do not assume two resolvers agree.
- **Large answers may need TCP.** UDP messages were traditionally limited to 512 bytes (that is the buffer size in the demo script); a client must be ready to retry over TCP.

## Exercise

Extend the toy server to answer `AAAA` for `shop.test` with `::1`, and decide what it should return for a `.test` name asked with type `MX`. Then check your answer with `dig`.

## What's next

The next post is "TCP: the handshake and connection states". With the name turned into an address, the client can finally open a connection, and that is where `connection refused`, timeouts and a pile of `TIME_WAIT` sockets come from.
