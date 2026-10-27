+++
date = '2027-01-02T10:00:00+03:30'
draft = false
title = 'DNS in practice'
description = 'DNS in practice with real dig runs, a query built by hand with Python struct and a tiny authoritative server in Go: records, TTL, NXDOMAIN and delegation.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "dns", "dig", "udp", "go", "python"]
cover = { image = "/images/covers/net-dns-in-practice.png", alt = "DNS in practice", hiddenInSingle = true }
+++

In [the previous post](/posts/net-addressing-subnets/) we computed with IP addresses, but nobody types them. People type names, and {{< term "dns" "DNS" >}} turns them into addresses. We met the layers in [the TCP/IP model post](/posts/net-tcp-ip-model/): DNS is an application protocol that usually rides on {{< term "udp" "UDP" >}}. This time we read real answers with `dig`, build a query byte by byte and write a tiny server.

> macOS (arm64), Go 1.26, Python 3.14, `dig` 9.10. Every `dig` names the public resolver `1.1.1.1` explicitly, so my own resolver address never appears; where I removed or replaced something I say so. Loopback demos use `127.0.0.1`. I did not measure any timings.

## Reading records

`example.com` is reserved for documentation (RFC 2606, according to the docs), so it is safe to query. Answer sections only:

```
example.com. 177   IN A     172.66.147.243
example.com. 177   IN A     104.20.23.154
example.com. 77    IN AAAA  2606:4700:10::6814:179a
example.com. 84087 IN NS    hera.ns.cloudflare.com.
example.com. 168   IN MX    0 .
example.com. 300   IN TXT   "v=spf1 -all"
example.com. 1048  IN SOA   elliott.ns.cloudflare.com. dns.cloudflare.com. 2418004112 ...
```

(AAAA shows one of two lines, SOA is shortened, and the TXT record has a second line I dropped.) `A` is IPv4, `AAAA` is IPv6, `NS` names the servers that own the zone, `SOA` holds the zone's serial and timers, and `TXT` is free text, here an SPF policy. The `MX` record `0 .` means "this domain accepts no mail". The second column is the {{< term "ttl" "TTL" >}}.

## TTL and caching

I asked the same question twice, six seconds apart:

```
example.com. 109 IN A 172.66.147.243
example.com. 29  IN A 104.20.23.154
```

The TTL went down, so the answer came from a cache. It dropped by 80, not 6; I did not investigate, but a big public resolver is many machines, each with its own cache.

## NXDOMAIN

```
$ dig @1.1.1.1 nonexistent-name.invalid A
status: NXDOMAIN
```

{{< term "nxdomain" "NXDOMAIN" >}} means the name does not exist. A surprise: `nonexistent-name.example.com` returned `status: NOERROR` with an empty answer and a SOA in the authority section. Either the name exists with no record of that type or the zone does something clever; either way `NOERROR` is not "found". Resolvers also cache negative answers, for a time derived from the SOA.

## Who answers: recursive versus authoritative

`1.1.1.1` is a {{< term "recursive-resolver" "recursive resolver" >}}: it does the work for you and caches. `dig +trace` does that work itself, starting from the root. Names only:

```
.            NS a.root-servers.net. ... m.root-servers.net.
com.         NS a.gtld-servers.net. ... m.gtld-servers.net.
example.com. NS hera.ns.cloudflare.com. / elliott.ns.cloudflare.com.
example.com. A  172.66.147.243 / 104.20.23.154
```

Root points to the `com` servers, `com` points to the domain's own name servers, and those hold the real data. They are the {{< term "authoritative-server" "authoritative servers" >}}.

## A query by hand

A DNS message is a 12-byte header (id, flags, four counts) plus a question: the name as length-prefixed labels, a type and a class. Python's `struct` is enough (`rawdns.py`):

```python
header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)  # RD set
qname = b"\x07example\x03com\x00"
q = header + qname + struct.pack("!HH", 1, 1)               # A, IN
```

Sent to `1.1.1.1:53` over UDP, then over {{< term "tcp" "TCP" >}} with a 2-byte length prefix:

```
query: 29 bytes
UDP reply 61 bytes
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 61 A 172.66.147.243
  name bytes: c00c example.com TTL 61 A 104.20.23.154
TCP reply 61 bytes (2-byte length prefix)
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 155 A 104.20.23.154
```

`QR=1` marks a response, `RCODE=0` is success and `ANCOUNT=2` counts the answers. The name in each answer is `c00c`: the top two bits `11` mean "pointer", and the remaining 14 bits (`0x00C` = 12) point to offset 12, where the question's name sits. That is name compression.

## A tiny authoritative server

`toy/main.go` listens on UDP `127.0.0.1:5300` (not 5353: macOS already uses it) and answers A queries under `.test`, a reserved TLD, with `127.0.0.1`; anything else gets NXDOMAIN. Real `dig`:

```
$ dig @127.0.0.1 -p 5300 shop.test
;; flags: qr aa rd; QUERY: 1, ANSWER: 1
shop.test.  30 IN A 127.0.0.1
$ dig @127.0.0.1 -p 5300 api.shop.test +short
127.0.0.1
$ dig @127.0.0.1 -p 5300 example.com
status: NXDOMAIN
```

`aa` is the authoritative flag; dig warns that recursion is not available, which is right.

## The resolver inside your program

Go's `net.Resolver` takes a custom `Dial`, so pointing it at the toy server takes three lines:

```
shop.test [127.0.0.1] <nil>
missing.example.com [] lookup missing.example.com no such host
```

(The real error also names the system resolver's address; I removed it.) Python's `socket.getaddrinfo` goes through the OS: `localhost` gave `127.0.0.1`, and `example.com` gave its two public IPv4 addresses. The OS consults `/etc/hosts` and the configured resolvers in an order set by system configuration; I describe it in words and did not paste it. Go can use its own pure-Go resolver or the C library's: with `GODEBUG=netdns=go` and `netdns=cgo` both resolved `localhost` and `example.com`, and that is all I claim.

## A few things to watch

- Many "slow requests" are slow lookups: a cache miss costs several round trips, and a failing resolver adds a timeout before the real request starts. A later case-study post chases one down.
- A low TTL means fast changes but more lookups; a high one the opposite.
- `NOERROR` with an empty answer is not NXDOMAIN.
- Answers can be reordered between queries, so do not depend on the first address.
- Large answers may need TCP; a client must be ready for it.

## Exercise

Extend the toy server to answer AAAA for `shop.test` with `::1`, and decide what it should return for a `.test` name asked with type MX.

## What's next

Next is "TCP: the handshake and connection states".
