+++
date = '2026-12-25T10:00:00+03:30'
draft = false
title = 'IP addressing and subnets'
description = 'IP addressing and subnets explained with real Go and Python runs: CIDR, netmask, host counts, splitting a /24, IPv6 basics and longest-prefix match.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "ip", "subnet", "cidr", "ipv6", "go", "python"]
cover = { image = "/images/covers/net-addressing-subnets.png", alt = "IP addressing and subnets", hiddenInSingle = true }
+++

In the [previous post](/posts/net-tcp-ip-model/) we followed a packet through the layers. The network layer put an address on it, and I skipped over how those addresses work. They are the part you meet daily: a security group rule, a Kubernetes pod range, a VPN that clashes with the office network. All of it is arithmetic on bits, so we will compute it with `net/netip` in Go and `ipaddress` in Python.

> Everything ran on macOS (arm64) with Go 1.26 and Python 3.14. All addresses are from the documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or invented. The only real system fact is the loopback lines from `ifconfig lo0`, reduced to those lines.

## An IPv4 address is a 32-bit number

The dotted form is four bytes written in decimal:

```go
a := netip.MustParseAddr("192.0.2.130")
b := a.As4()
fmt.Println(binary.BigEndian.Uint32(b[:]))
```

```
192.0.2.130 3221226114 11000000000000000000001010000010
```

Python's `int(ip_address(...))` gives the same integer.

## Prefix, netmask and the network address

A {{< term "cidr" "CIDR" >}} prefix like `/24` says how many leading bits identify the network. The rest identify the host. The {{< term "netmask" "netmask" >}} is the same idea written as an address: `/24` is 24 ones then 8 zeros, `255.255.255.0`. The network address is the address ANDed with the mask. My helper prints each:

```
192.0.2.77/24    network=192.0.2.0      mask=255.255.255.0   last=192.0.2.255    hosts=254
198.51.100.0/30  network=198.51.100.0   mask=255.255.255.252 last=198.51.100.3   hosts=2
198.51.100.4/31  network=198.51.100.4   mask=255.255.255.254 last=198.51.100.5   hosts=2
203.0.113.9/32   network=203.0.113.9    mask=255.255.255.255 last=203.0.113.9    hosts=1
```

Classic rule: a {{< term "subnet" "subnet" >}} has 2^(32-prefix) addresses, minus the network address and the broadcast address, so `/24` has 254 hosts and `/30` has 2. Two prefixes are special. A `/32` is one address. A `/31` has no room for those two reserved addresses, and I believe RFC 3021 allows both addresses to be used on point-to-point links; Python's `hosts()` returns both for `/31` and the one address for `/32`, which matches. Python also refuses `ip_network("192.0.2.5/24")` with `192.0.2.5/24 has host bits set`, while Go's `Masked()` quietly clears them.

## Splitting and joining

```python
n = ipaddress.ip_network("192.0.2.0/24")
list(n.subnets(new_prefix=26))
```

```
['192.0.2.0/26', '192.0.2.64/26', '192.0.2.128/26', '192.0.2.192/26']
```

Go printed the same four. Going up, `supernet(new_prefix=24)` of `192.0.2.64/26` gives `192.0.2.0/24`, and `collapse_addresses` merged `192.0.2.0/25` and `192.0.2.128/25` into one `/24`. Membership is `Contains` in Go and `in` in Python: `192.0.2.130` is inside, `192.0.3.1` is not.

## Special ranges

I printed what the libraries say:

| address | Go IsPrivate | Python is_private | Python is_global |
|---|---|---|---|
| 10.1.2.3 | true | True | False |
| 100.64.0.1 (CGNAT) | false | False | False |
| 169.254.1.1 | false | True | False |
| 192.0.2.1 (docs) | false | True | False |
| 8.8.8.8 | false | False | True |

The RFC 1918 private ranges are `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16`: `172.16.0.1` is in, `172.32.0.1` is out. The libraries disagree on edges: Go's `IsPrivate` means exactly RFC 1918, Python's `is_private` also covers link-local and documentation ranges. `100.64.0.0/10` is carrier-grade NAT space: neither private nor global by either library, a common trap in VPN setups. `127.0.0.0/8` is {{< term "loopback" "loopback" >}} and `169.254.0.0/16` is link-local. Note that Go's `IsGlobalUnicast` is true for private and documentation addresses, so it does not mean "reachable on the internet".

The only real fact from this machine:

```
$ ifconfig lo0 | grep inet      # other lines removed
	inet 127.0.0.1 netmask 0xff000000
	inet6 ::1 prefixlen 128
```

## IPv6 in short

{{< term "ipv6" "IPv6" >}} addresses have 128 bits, written as eight groups of hex. Leading zeros drop and one run of zero groups becomes `::`. Real round trips:

```
2001:0db8:0000:0000:0000:0000:0000:0001 -> 2001:db8::1
2001:db8:0:0:1:0:0:1 -> 2001:db8::1:0:0:1
0:0:0:0:0:0:0:1 -> ::1
```

The second shows the rule: only one `::` is allowed, so the longest zero run is chosen. A LAN subnet is normally a `/64`: `2001:db8:abcd:12::/64` contains `...12::ff` and not `...13::1`. `fe80::/10` is link-local, `::1` is loopback. IPv6 has no broadcast; it uses multicast instead.

## Longest-prefix match

A router holds a table of prefixes and next hops, and the most specific matching prefix wins. My invented table: `0.0.0.0/0` via gateway-A, `10.0.0.0/8` core-B, `10.1.0.0/16` site-C, `10.1.2.0/24` lab-D, `192.0.2.0/24` dmz-E. The lookup is a linear scan keeping the longest match; a second version walks a binary trie, one bit per level:

```
10.1.2.9     -> 10.1.2.0/24 via lab-D     trie=lab-D
10.1.9.9     -> 10.1.0.0/16 via site-C    trie=site-C
10.200.0.1   -> 10.0.0.0/8 via core-B    trie=core-B
192.0.2.50   -> 192.0.2.0/24 via dmz-E     trie=dmz-E
203.0.113.5  -> 0.0.0.0/0  via gateway-A trie=gateway-A
```

`10.1.2.9` matches four routes; the `/24` wins. The `/0` default route catches everything else. Both versions agree. This is a toy, not how a kernel does it.

## A few things to watch

- Host counts: usable hosts are 2^h - 2, but not for `/31` and `/32`.
- Overlaps: my check found `10.0.0.0/24` overlaps `10.0.0.128/25`. Use `Overlaps` before you add a subnet; clashes are painful later.
- Host bits: `192.0.2.5/24` is an address with a prefix, not a network. Parse accordingly.
- Bad input errors clearly: `192.0.2.0/33` gives `prefix length out of range`, and `192.0.2.256` gives `IPv4 field has value >255`.

## Exercise

Split `198.51.100.0/24` into one `/25` and two `/26`, check there is no overlap, then add them to the routing table and look up three addresses.

## What's next

Next is "DNS in practice": how a name becomes one of these addresses.
