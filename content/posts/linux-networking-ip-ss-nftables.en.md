+++
date = '2027-05-14T10:00:00+03:30'
draft = false
title = 'Linux networking: ip, ss and nftables'
description = 'Linux networking from the man pages: reading ip and ss, nftables hooks and a default-drop server rule set, plus a Go linter and /proc/net/tcp parser.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "networking", "iproute2", "ss", "nftables", "firewall", "go", "macos"]
cover = { image = "/images/covers/linux-networking-ip-ss-nftables.png", alt = "Linux networking: ip, ss and nftables", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. This is the ninth post of the Linux series, after [I/O and epoll](/posts/linux-io-epoll/). Sockets are now in the kernel's hands, so how do you inspect them and decide which packets may reach them? Facts come from man pages and kernel docs; Linux-looking text is labelled "illustrative, not captured", with documentation addresses only. Background: [IP addressing and subnets](/posts/net-addressing-subnets/) and [TCP: the handshake and connection states](/posts/net-tcp-handshake-states/).

## ip: addresses, routes, neighbours

The {{< term "iproute2" "iproute2" >}} tools are driven by one command, `ip`. Its man page lists the objects `address`, `link`, `route`, `neigh` and `netns`, among others. I did not find a "replaces ifconfig" sentence there, so I only say that these are the tools current Linux documentation uses.

Illustrative, not captured:

```
$ ip -br addr
lo     UNKNOWN  127.0.0.1/8
eth0   UP       192.0.2.10/24
$ ip route
default via 192.0.2.1 dev eth0
192.0.2.0/24 dev eth0 proto kernel scope link src 192.0.2.10
$ ip route get 203.0.113.5
203.0.113.5 via 192.0.2.1 dev eth0 src 192.0.2.10
```

Routing picks the most specific matching prefix (longest match), and `default` is the zero-length prefix that matches everything; see {{< term "cidr" "CIDR" >}} in the addressing post. `ip neigh` shows the neighbour table, the IP-to-MAC cache for the local link.

## ss: sockets

`ss -tlnp` means TCP (`-t`), listening only (`-l`), numeric (`-n`), with processes (`-p`); `-s` prints summary statistics. The man page I fetched does not explain `Recv-Q` and `Send-Q`. As I understand it, for a listening socket they show the current accept queue length and its limit, the {{< term "listen-backlog" "listen backlog" >}}; that is the kernel's sock_diag convention and I did not verify it here. For connected sockets they are unread and unacknowledged bytes.

Illustrative, not captured:

```
$ ss -tlnp
State  Recv-Q Send-Q Local Address:Port Peer Address:Port
LISTEN 0      4096   0.0.0.0:22         0.0.0.0:*
LISTEN 0      511    127.0.0.1:8080     0.0.0.0:*
```

A pile of sockets in {{< term "time-wait" "TIME-WAIT" >}} is normal for a busy client; many in CLOSE-WAIT usually mean the application forgot to `close()`.

## Reading /proc/net/tcp for real

The kernel doc for `/proc/net/tcp` says the interface is deprecated in favour of tcp_diag, but it still shows what `ss` reads. An address looks like `0100007F:1F90`, hexadecimal. The doc's own example `010310AC` is 172.16.3.1, so on a little-endian host the IPv4 bytes come reversed. The state is a hex number from `include/net/tcp_states.h`: 01 ESTABLISHED, 06 TIME_WAIT, 08 CLOSE_WAIT, 0A LISTEN.

I wrote a small Go program that decodes this and counts states. Its input is an **invented** fixture in that format (documentation addresses), not this Mac's sockets. It ran for real, with passing unit tests:

```
$ lx9 tcp testdata/proc_net_tcp.txt
127.0.0.1:8080         0.0.0.0:0              LISTEN
0.0.0.0:22             0.0.0.0:0              LISTEN
192.0.2.10:443         203.0.113.5:50000      ESTABLISHED
...
CLOSE_WAIT   1
ESTABLISHED  2
LISTEN       2
TIME_WAIT    3
```

(Middle rows trimmed.) On Linux you would point it at the real file; I did not.

## nftables: tables, chains, hooks

{{< term "nftables" "nftables" >}} is configured with `nft`. Per its man page, a rule set is made of tables, chains and rules. A base chain is attached to a {{< term "netfilter" "netfilter" >}} hook (`prerouting`, `input`, `forward`, `output`, `postrouting`) with a priority; lower numbers run first. Inbound traffic for this host goes through `input`, forwarded traffic through `forward`. The chain's `policy` is `accept` by default or `drop`. A `drop` or `reject` verdict ends evaluation; `accept` only ends the current base chain, so a later chain can still drop the packet. {{< term "connection-tracking" "Connection tracking" >}} gives rules `ct state` (new, established, related), and NAT chains use the same machinery.

A server rule set, written as text (this is the input of my linter, and `nft -c -f file` is the real syntax check, which I did not run):

```
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        iif "lo" accept
        ct state established,related accept
        tcp dport 22 ct state new limit rate 10/minute accept
        tcp dport { 80, 443 } accept
        log prefix "drop: " drop
    }
}
```

## A linter, not a parser

My linter checks three things in the input chain: policy drop, an established/related accept, and a loopback accept. It is regexps on lines, **not** nft's parser; passing it proves nothing about validity. Real output on the good file and on a copy with the policy changed to accept and the established rule deleted:

```
$ lx9 lint testdata/good.nft
OK: 3 checks passed
$ lx9 lint testdata/bad.nft
FAIL: input chain policy is not drop
FAIL: no 'ct state established,related accept' in input chain
```

The program also passed `GOOS=linux GOARCH=arm64 go vet ./... && go build`; it was never run on Linux.

## Namespaces and veth

Containers get their own network stack through a network {{< term "namespace" "namespace" >}}, see [cgroups and namespaces](/posts/linux-cgroups-namespaces/). Per the ip-netns and ip-link man pages, `ip netns add net0` creates one and `ip link add ... type veth` creates a {{< term "veth" "veth" >}} pair, two virtual interfaces joined like a cable; move one end into the namespace with `ip link set ... netns net0`. Not run.

## A few things to watch

- Start from default drop, but keep an out-of-band console: a wrong rule over SSH locks you out.
- Allow `iif "lo"` and established/related first, or local services and replies break.
- Rate-limit new connections on exposed ports.
- Check syntax with `nft -c -f` before applying.
- Docs I read are the man pages; versions differ.

## Exercise

On a throwaway VM, run `ss -tlnp`, then `ss -tan` while one `curl` is open, and compare with `/proc/net/tcp`.

## What's next

The next post is “SSH and keys”.
