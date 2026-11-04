+++
date = '2026-12-25T10:00:00+03:30'
draft = false
title = 'IP addressing and subnets'
description = 'IP addressing and subnets explained with real Go and Python runs: CIDR, netmask, host counts, splitting a /24, IPv6 basics and longest-prefix match.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "ip", "subnet", "cidr", "ipv6", "go", "python"]
cover = { image = "/images/covers/net-addressing-subnets.png", alt = "IP addressing and subnets", hiddenInSingle = true }
+++

Two servers have the addresses `192.0.2.10` and `192.0.2.200`. Can they talk to each other directly, or does their traffic have to go through a router? You cannot tell from the two addresses alone. If the network is configured as `192.0.2.0/24`, they are neighbours. If it is `192.0.2.0/26`, they are not. The number after the slash decides, and this small piece of arithmetic is behind a lot of everyday problems: a cloud security-group rule that is too wide or too narrow, a Kubernetes pod range that overlaps another one, a VPN that clashes with the office network.

The good news is that it really is only arithmetic on bits. The [previous post](/posts/net-tcp-ip-model/) followed a packet through the layers and showed an address as four bytes in a header, without explaining how addresses are grouped. This post does that, with real code: `net/netip` in Go and `ipaddress` in Python. No networking background is needed, only counting in binary, which I explain as we go.

> Everything ran on macOS (arm64) with Go 1.27.3 and Python 3.14. All addresses come from the ranges reserved for documentation (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or are invented. The only real fact from my machine is the loopback lines of `ifconfig lo0`, reduced to those lines. The demo code was first written with Go 1.26; the outputs below are from a fresh run.

## An IPv4 address is one 32-bit number

An IPv4 address like `192.0.2.130` is written as four numbers separated by dots, but it is really a single 32-bit number. Each of the four parts is one byte (0 to 255). You can compute the number yourself: each byte is worth 256 times more than the one to its right.

```
192 * 256^3 + 0 * 256^2 + 2 * 256 + 130 = 3221225472 + 0 + 512 + 130 = 3221226114
```

Go confirms it, and also prints the 32 bits:

```go
a := netip.MustParseAddr("192.0.2.130")
b := a.As4()
fmt.Println(binary.BigEndian.Uint32(b[:]))
```

```
192.0.2.130 3221226114 11000000000000000000001010000010
```

Read the bits in groups of eight: `11000000` is 192, `00000000` is 0, `00000010` is 2, and `10000010` is 130. Python's `int(ip_address(...))` gives the same integer. Keep this picture in mind: an address is a row of 32 bits, and everything below is about where we draw a line in that row.

## The prefix: where the network ends and the host begins

Every address has two parts. The first bits say which **network** the machine is in, the remaining bits say which **host** it is inside that network. It is like a phone number: the area code first, then the local number. The **prefix length** tells how many bits belong to the network part. It is written after a slash, for example `/24`, and this notation is called {{< term "cidr" "CIDR" >}}.

The same idea can be written as an address instead, the {{< term "netmask" "netmask" >}}: ones for the network bits, zeros for the host bits. `/24` is 24 ones followed by 8 zeros, which is `255.255.255.0`. And the **network address** is simply the address with all host bits set to zero, that is, the address AND-ed with the mask.

Let's do it by hand for `192.0.2.77` with a `/26` prefix. Only the last byte matters, because the first three bytes are fully inside the network part:

```
77            = 01001101
mask (/26)    = 11000000      (192, the first 26 bits are ones)
77 AND mask   = 01000000      = 64
```

So the network address is `192.0.2.64`. The network spans `192.0.2.64` to `192.0.2.127`, which is 64 addresses (2 to the power of the 6 host bits). Python agrees: `ip_interface("192.0.2.77/26").network` is `192.0.2.64/26`.

Now we can answer the opening question. A machine decides whether another address is a neighbour by comparing networks. If both have the same network address, it sends the packet directly. If not, it sends the packet to its **gateway**, a router that knows how to go further:

```
192.0.2.10/24  -> 192.0.2.200  same network: True   (network 192.0.2.0/24)
192.0.2.10/26  -> 192.0.2.200  same network: False  (network 192.0.2.0/26)
```

With `/24` the network is `192.0.2.0` to `192.0.2.255`, and `.200` is inside. With `/26` the network is only `192.0.2.0` to `192.0.2.63`, and `.200` is outside. (I ran this two-line check in a scratch script, not in the demo directory.)

### How many hosts fit?

A prefix of length *p* leaves 32 - *p* bits for hosts, so the network has 2^(32 - *p*) addresses. The classic rule takes two away: the first address (the network address itself) and the last one (the **broadcast** address, which means "everyone on this network"). The demo prints a few examples with its own helper:

```
192.0.2.77/24    network=192.0.2.0      mask=255.255.255.0   last=192.0.2.255    hosts=254
198.51.100.0/30  network=198.51.100.0   mask=255.255.255.252 last=198.51.100.3   hosts=2
198.51.100.4/31  network=198.51.100.4   mask=255.255.255.254 last=198.51.100.5   hosts=2
203.0.113.9/32   network=203.0.113.9    mask=255.255.255.255 last=203.0.113.9    hosts=1
```

A `/24` has 256 addresses and 254 hosts. A `/30` has 4 addresses and 2 hosts, which is exactly enough for two routers connected by a cable. The last two lines are special. A `/32` is a single address, a network of one. A `/31` has only two addresses, so there is no room to give up two of them. As far as I know, RFC 3021 allows both addresses to be used on point-to-point links; Python's `hosts()` returns both for `/31` and the one address for `/32`, which matches.

Notice the first line: I gave the helper `192.0.2.77/24` (an address with a prefix) and it printed the network `192.0.2.0`. Python is stricter here. `ip_network("192.0.2.5/24")` fails with `192.0.2.5/24 has host bits set`, because a network should have zeros in the host part. Go's `Masked()` quietly clears those bits instead. Both are reasonable; just know which one your tool does.

## Splitting and joining networks

A big network can be divided into smaller ones by moving the line to the right. Each extra bit in the prefix halves the network. Splitting `192.0.2.0/24` into `/26` takes two extra bits, so we get four networks of 64 addresses each:

```python
n = ipaddress.ip_network("192.0.2.0/24")
list(n.subnets(new_prefix=26))
```

```
['192.0.2.0/26', '192.0.2.64/26', '192.0.2.128/26', '192.0.2.192/26']
```

Each one is called a {{< term "subnet" "subnet" >}}. Go prints the same four. The step between them is 64, so each starts where the previous one ended, and `192.0.2.64/26` is the same one we computed by hand above.

The opposite also works. `supernet(new_prefix=24)` on `192.0.2.64/26` gives `192.0.2.0/24` again, and `collapse_addresses` merges `192.0.2.0/25` and `192.0.2.128/25` into the single `192.0.2.0/24`. To ask "is this address inside that network?", use `Contains` in Go and `in` in Python. In the demo, `192.0.2.130` is inside `192.0.2.0/24` and `192.0.3.1` is not.

## Special ranges you will meet

Not every address is a normal public one. A few ranges have fixed meanings, and you will see them often:

- `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16` are the **private** ranges from RFC 1918. They are not routed on the public internet, so every company and every home can reuse them. `172.16.0.1` is inside the second range and `172.32.0.1` is outside it.
- `100.64.0.0/10` is shared address space for carrier-grade NAT, used by some providers. It is not private and not global, which makes it a classic trap in VPN setups.
- `127.0.0.0/8` is {{< term "loopback" "loopback" >}}: the machine itself.
- `169.254.0.0/16` is link-local: addresses a machine gives itself when it finds no configuration.
- `192.0.2.0/24`, `198.51.100.0/24` and `203.0.113.0/24` are reserved for documentation, which is why they appear in this post.

I asked both libraries what they think of a few addresses:

| address | Go `IsPrivate` | Python `is_private` | Python `is_global` |
|---|---|---|---|
| 10.1.2.3 | true | True | False |
| 100.64.0.1 (CGNAT) | false | False | False |
| 169.254.1.1 | false | True | False |
| 192.0.2.1 (docs) | false | True | False |
| 8.8.8.8 | false | False | True |

The libraries disagree at the edges. Go's `IsPrivate` means exactly RFC 1918, so link-local and documentation addresses are `false`. Python's `is_private` is broader and also covers link-local and documentation ranges. `100.64.0.1` is neither private nor global in either library. Be careful with Go's `IsGlobalUnicast`: it returned `true` for the private and documentation addresses in my run, so it does not mean "reachable on the internet". It only means "not loopback, link-local, multicast or the like".

The one real fact from this machine is the loopback lines. I printed only these two lines of `ifconfig lo0`; the full output of other interfaces would reveal my network, so I left it out:

```
$ ifconfig lo0 | grep inet      # first two lines only
	inet 127.0.0.1 netmask 0xff000000
	inet6 ::1 prefixlen 128
```

`0xff000000` is the mask in hex: eight ones, then 24 zeros, which is `255.0.0.0` or `/8`. That matches `127.0.0.0/8`.

## IPv6 in short

{{< term "ipv6" "IPv6" >}} uses the same prefix idea with 128 bits instead of 32. An address is written as eight groups of four hex digits, and two rules make it shorter: leading zeros in a group can be dropped, and one run of all-zero groups can be replaced by `::`. These real round trips from the demo show both rules:

```
2001:0db8:0000:0000:0000:0000:0000:0001 -> 2001:db8::1
2001:db8:0:0:1:0:0:1 -> 2001:db8::1:0:0:1
0:0:0:0:0:0:0:1 -> ::1
```

The second line shows why only one `::` is allowed: there are two runs of zeros, and if both were replaced you could not tell how many groups each one stands for. The longest run is chosen. The last line is the IPv6 loopback address.

A normal IPv6 network is a `/64`, so 64 bits are left for hosts. In the demo, `2001:db8:abcd:12::/64` contains `2001:db8:abcd:12::ff` (`true`) and does not contain `2001:db8:abcd:13::1` (`false`). Other ranges to know: `fe80::/10` is link-local, and `::1` is loopback. IPv6 has no broadcast; it uses multicast, where a packet goes to a group of subscribers, instead.

## Longest-prefix match: how a router chooses

Back to the machine that must decide where to send a packet. A router does the same, but with a whole table of networks. Each entry says: "packets for this prefix go through that next hop". Several entries can match one destination. The rule is simple: **the most specific one wins**, that is, the matching prefix with the most bits.

My invented table has five entries: `0.0.0.0/0` via `gateway-A`, `10.0.0.0/8` via `core-B`, `10.1.0.0/16` via `site-C`, `10.1.2.0/24` via `lab-D` and `192.0.2.0/24` via `dmz-E`. The prefix `0.0.0.0/0` has zero network bits, so it matches everything: it is the **default route**, the catch-all.

The demo looks up five addresses in two ways: a plain loop over all entries that keeps the longest match, and a binary trie, a tree that walks the address one bit per level. This is what they print:

```
10.1.2.9     -> 10.1.2.0/24 via lab-D     trie=lab-D
10.1.9.9     -> 10.1.0.0/16 via site-C    trie=site-C
10.200.0.1   -> 10.0.0.0/8 via core-B    trie=core-B
192.0.2.50   -> 192.0.2.0/24 via dmz-E     trie=dmz-E
203.0.113.5  -> 0.0.0.0/0  via gateway-A trie=gateway-A
```

Take the first line. `10.1.2.9` matches four of the five entries: the default route, the `/8`, the `/16` and the `/24`. The `/24` is the longest, so `lab-D` wins. `10.1.9.9` is not in `10.1.2.0/24`, so it falls back to the `/16`. `203.0.113.5` matches only the default route. The loop and the trie agree on every line. This is a toy; a real router (or kernel) uses much more optimised structures, but the rule is the same.

## Where subnet math bites

- **Host counts.** Usable hosts are 2^h - 2 for h host bits, except `/31` and `/32`. Cloud providers may also reserve a few addresses per subnet for themselves, so check your provider's documentation before you size a subnet tightly.
- **Overlaps.** The demo's overlap check found that `10.0.0.0/24` overlaps `10.0.0.128/25`, because the second is inside the first. Overlapping ranges are cheap to prevent and painful to fix later, for example when you want to connect two networks that both use `10.0.0.0/16`. Call `Overlaps` before you add a subnet.
- **Host bits.** `192.0.2.5/24` is an address with a prefix, not a network. Make sure you know whether your tool wants an interface address or a network, and what it does with the host bits.
- **Bad input.** Parsing fails with clear messages: `192.0.2.0/33` gives `prefix length out of range` and `192.0.2.256` gives `IPv4 field has value >255`. Treat these as input errors, not as bugs.

## Exercise

Split `198.51.100.0/24` into one `/25` and two `/26`, check that no two of them overlap, then add them to the routing table with next hops of your choice and look up three addresses.

## What's next

The next post is "DNS in practice". People do not type addresses like these; they type names. DNS is how a name becomes one of these addresses, and it is the step that happens before your first packet is sent.
