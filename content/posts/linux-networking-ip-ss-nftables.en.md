+++
date = '2027-05-14T10:00:00+03:30'
draft = false
title = 'Linux networking: ip, ss and nftables'
description = 'Linux networking from the man pages: reading ip and ss, nftables hooks and a default-drop server rule set, plus a Go linter and /proc/net/tcp parser.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "networking", "iproute2", "ss", "nftables", "firewall", "go", "macos"]
cover = { image = "/images/covers/linux-networking-ip-ss-nftables.png", alt = "Linux networking: ip, ss and nftables", hiddenInSingle = true }
+++

Two small stories every Linux administrator knows. In the first, you add a firewall rule, everything works, you go home, and after the next reboot the rule is gone. In the second, you tighten the firewall over SSH, press Enter, and your own session freezes, because the new rule blocked the very connection you were typing through. Both come from not being clear about what the firewall is, where its rules live and how they are evaluated.

So this post covers three tools in order of risk. First `ip`, which shows how the machine is connected to the network. Then `ss`, which shows the sockets the kernel holds, the ones we met in [I/O and epoll](/posts/linux-io-epoll/). Then nftables, the part that decides which packets may reach those sockets at all. The first two only look. The third can lock you out.

As in the last posts, I wrote this on a Mac, not on Linux. The facts come from the man pages and kernel docs, and anything that looks like Linux output is labelled "illustrative, not captured" and uses only documentation addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). If you need background on addresses and connection states, see [IP addressing and subnets](/posts/net-addressing-subnets/) and [TCP: the handshake and connection states](/posts/net-tcp-handshake-states/).

## ip: addresses, routes, neighbours

The {{< term "iproute2" "iproute2" >}} tools are driven by one command, `ip`. Its man page lists the objects it manages: `address`, `link`, `route`, `neigh` and `netns`, among others. People often say `ip` replaced `ifconfig`; I did not find a sentence saying so in the man page, so I only say that `ip` is what current Linux documentation uses.

Here is what the three most common commands look like, illustrative, not captured:

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

The first command lists interfaces in a brief form: `lo` is the loopback interface (the machine talking to itself) and `eth0` is the network card with address `192.0.2.10` in a `/24` network. The second command prints the routing table. The first line says "anything not matched below goes through the gateway `192.0.2.1`"; the second says "the local `/24` is directly reachable on `eth0`". The third command asks the kernel a question: "if I send to `203.0.113.5`, which way does it go?". The answer is via the gateway, out of `eth0`, with `192.0.2.10` as the source address.

How does the kernel choose between routes? It takes the most specific matching prefix (the longest match), and `default` is the zero-length prefix that matches everything, so it wins only when nothing else matches. If prefixes are new to you, see {{< term "cidr" "CIDR" >}} in the addressing post. One more table: `ip neigh` shows the neighbour table, the cache that maps IP addresses to MAC addresses on the local link.

## ss: sockets

`ss` lists the sockets in the kernel. The most useful form is `ss -tlnp`: TCP (`-t`), listening only (`-l`), numeric ports and addresses (`-n`), and the owning process (`-p`). `ss -s` prints summary statistics.

The columns `Recv-Q` and `Send-Q` deserve care. The man page I fetched does not explain them. As I understand it, for a listening socket they show the current length of the accept queue and its limit, the {{< term "listen-backlog" "listen backlog" >}}; that is the kernel's sock_diag convention and I did not verify it here. For connected sockets they are bytes not yet read by the application and bytes not yet acknowledged by the peer. Illustrative, not captured:

```
$ ss -tlnp
State  Recv-Q Send-Q Local Address:Port Peer Address:Port
LISTEN 0      4096   0.0.0.0:22         0.0.0.0:*
LISTEN 0      511    127.0.0.1:8080     0.0.0.0:*
```

Line by line: something listens on port 22 on every interface (`0.0.0.0`), probably an SSH server, and something listens on port 8080 only on loopback, so only this machine can reach it. That loopback detail is exactly the kind of fact `ss` is good for: "is my service listening where I think it is?".

Counting sockets by state also tells stories. A pile of sockets in {{< term "time-wait" "TIME-WAIT" >}} is normal for a busy client. Many sockets stuck in CLOSE-WAIT usually mean the application forgot to call `close()` after the peer closed.

## Reading /proc/net/tcp for real

`ss` gets its information from the kernel, and an older interface still shows the same data as text: `/proc/net/tcp`. The kernel docs say this interface is deprecated in favour of tcp_diag, but it is a good way to see what a socket listing really contains. It is also where I had something to run.

The file has one line per socket, and the addresses are in hexadecimal, like `0100007F:1F90`. The part after the colon is the port: `1F90` is 8080. The part before it is the IPv4 address as four bytes written in the host's byte order. The docs' own example is `010310AC`, which is 172.16.3.1, so on a little-endian machine the bytes come out reversed: read them from the right. The state is a hex number from `include/net/tcp_states.h`: 01 is ESTABLISHED, 06 TIME_WAIT, 08 CLOSE_WAIT and 0A LISTEN.

I wrote a small Go program, `lx9`, that decodes a file in this format and counts the states. Its input is an **invented** fixture (documentation addresses), not this Mac's sockets, since this Mac has no such file. The program and its unit tests ran for real, and the tests pass:

```
$ lx9 tcp testdata/proc_net_tcp.txt
127.0.0.1:8080         0.0.0.0:0              LISTEN
0.0.0.0:22             0.0.0.0:0              LISTEN
192.0.2.10:443         203.0.113.5:50000      ESTABLISHED
192.0.2.10:443         198.51.100.7:50001     ESTABLISHED
192.0.2.10:443         203.0.113.5:50002      TIME_WAIT
192.0.2.10:443         203.0.113.5:50003      TIME_WAIT
192.0.2.10:443         198.51.100.7:50004     TIME_WAIT
192.0.2.10:443         198.51.100.7:50005     CLOSE_WAIT

CLOSE_WAIT   1
ESTABLISHED  2
LISTEN       2
TIME_WAIT    3
```

The first block has one row per socket: local address, remote address, state. The second block counts states. A server with two listeners, two active clients and a few connections in the closing phase looks like this. On Linux you would point the program at the real file; I did not.

## nftables: tables, chains, hooks

Now the part that can lock you out. The firewall in the Linux kernel is called {{< term "netfilter" "netfilter" >}}, and {{< term "nftables" "nftables" >}} is the modern way to configure it, using the `nft` command. Per its man page, a rule set is built from three nested things:

- A **table** is a container for chains, tied to an address family (`inet` covers both IPv4 and IPv6).
- A **chain** is an ordered list of rules. A **base chain** is one attached to a netfilter **hook**, a point on the packet's path through the kernel: `prerouting`, `input`, `forward`, `output` or `postrouting`. It also has a priority, and lower numbers run first.
- A **rule** is a condition plus an action, such as "TCP packets to port 22: accept".

Which hook matters? Traffic addressed to this host passes through `input`. Traffic that the host merely forwards to another machine passes through `forward`. Traffic the host itself sends goes through `output`.

A base chain also has a `policy`, what happens to a packet that no rule decided: `accept` by default, or `drop`. Rules end with a verdict. A `drop` or `reject` verdict ends evaluation of the packet. An `accept` only ends the current base chain, so, according to the man page, a later chain can still drop the packet. {{< term "connection-tracking" "Connection tracking" >}} lets rules talk about whole connections instead of single packets: `ct state` can be `new`, `established` or `related`.

Here is a typical rule set for a server, written as text. It is also the input of my linter below, and `nft -c -f file` is the real syntax check, which I did not run because `nft` is not available here:

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

Read it top to bottom, the way the kernel does:

1. `type filter hook input priority filter; policy drop;` makes this a filtering chain on the `input` hook, and says anything not accepted below is dropped. This is "default deny".
2. `iif "lo" accept` accepts everything arriving on the loopback interface, so local services can talk to each other.
3. `ct state established,related accept` accepts packets that belong to connections already allowed. Without this, the replies to your own outgoing requests would be dropped.
4. `tcp dport 22 ct state new limit rate 10/minute accept` allows new SSH connections, at most ten per minute.
5. `tcp dport { 80, 443 } accept` allows web traffic.
6. `log prefix "drop: " drop` logs and drops whatever is left.

Order matters. Rule 3 is before rule 4 on purpose: your existing SSH session is "established", so it keeps working even if the "new" rate is used up.

## A linter, not a parser

Mistakes in a rule set are costly, so I wrote a small checker. It looks at the input chain and checks three things: the policy is drop, there is an established/related accept, and there is a loopback accept. It is regular expressions on lines, **not** nft's parser, so passing it proves nothing about whether the file is valid. What it does is catch the three mistakes I would least like to make. Real output on the good file, and on a copy where I changed the policy to accept and deleted the established rule:

```
$ lx9 lint testdata/good.nft
OK: 3 checks passed
$ lx9 lint testdata/bad.nft
FAIL: input chain policy is not drop
FAIL: no 'ct state established,related accept' in input chain
```

The bad file has the loopback rule, so only two checks fail. The program also passed `GOOS=linux go vet` and `go build` as a cross-compile check; it was never run on Linux (it does not need to be, since it only reads text).

## Namespaces and veth

Containers get their own network stack through a network {{< term "namespace" "namespace" >}}, as in [cgroups and namespaces: the base of containers](/posts/linux-cgroups-namespaces/). Per the ip-netns and ip-link man pages, `ip netns add net0` creates one, and `ip link add ... type veth` creates a {{< term "veth" "veth" >}} pair: two virtual interfaces joined like the two ends of a cable. You move one end into the namespace with `ip link set ... netns net0`, and the other end stays on the host. I have not run any of this.

## Firewall cautions

- **Start from default drop, but keep a way back in.** A wrong rule over SSH locks you out, so keep an out-of-band console, or apply new rules with a timer that undoes them.
- **Allow `iif "lo"` and established/related first.** Without them local services and replies to your own requests break.
- **Do not forget ICMP.** The rule set above allows no ICMP at all. I am certain that on IPv6 the neighbour discovery protocol runs over ICMPv6, so a default-drop `inet` firewall needs rules for it; a real rule set would add them.
- **Rate-limit new connections on exposed ports,** as the SSH rule does.
- **Check syntax before applying.** `nft -c -f file` checks a file without loading it.
- **A rule loaded with `nft` lives in kernel memory.** As I understand it, it is gone after a reboot unless the distribution loads a saved file at boot (the file's name and the service are distribution-specific; I did not verify them here). Saving what you changed is part of the job.
- **The docs I read are the man pages and kernel docs, and versions differ.** Check the pages on your machine.

## Exercise

On a throwaway VM, run `ss -tlnp`, then `ss -tan` while one `curl` is open, and compare what you see with `/proc/net/tcp`. Then take a copy of the sample rule set, add a rule of your own, and run the linter on it.

## What's next

The next post is "SSH and keys". It is the first thing a bad firewall rule breaks, and it shows how you can log in to a machine with a key instead of a password, without sending a secret.
