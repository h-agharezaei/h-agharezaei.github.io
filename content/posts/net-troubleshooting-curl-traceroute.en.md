+++
date = '2027-04-16T10:00:00+03:30'
draft = false
title = 'Network troubleshooting with curl, dig and traceroute'
seoTitle = 'Network troubleshooting with curl, dig, traceroute'
description = 'Network troubleshooting with curl, dig and traceroute: real exit codes, redirects, Host header, DNS answers, NXDOMAIN and a layer-by-layer checklist.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "troubleshooting", "curl", "dig", "traceroute", "dns"]
cover = { image = "/images/covers/net-troubleshooting-curl-traceroute.png", alt = "Network troubleshooting with curl, dig and traceroute", hiddenInSingle = true }
+++

In [the previous post](/posts/net-load-balancer-l4-l7/) a request crossed one more box on its way. When something breaks, the skill is to find which layer broke. This post is a small toolbox: curl for {{< term "http" "HTTP" >}}, dig for {{< term "dns" "DNS" >}}, nc and lsof for ports, traceroute for the path. It uses ideas from [the TCP/IP model](/posts/net-tcp-ip-model/), [DNS in practice](/posts/net-dns-in-practice/) and [HTTP/1.1 by hand](/posts/net-http1-by-hand/).

> Privacy: servers ran on `127.0.0.1:18080` (a small Go test server, macOS, curl 8.7.1). For DNS I always asked a public resolver explicitly and dropped the lines that name my machine or network. I did not paste any traceroute through the internet, because it lists real hops. The machine was busy, so no timings. `ss` and `ip` are Linux tools and I did not run them.

## curl: what did the server say

`curl -v` shows the request and response headers. One thing it showed: the `Host` header curl sent was `127.0.0.1:18080`. `-I` asks only for headers. `-w` prints facts about the transfer:

```
$ curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:18080/missing
http=404
```

A 404 or 500 is an answer, so curl exits with 0 for both. HTTP status and transport errors are different things.

## curl: when there is no answer

Exit codes are the real signal. All of these I ran:

```
--max-time 1 on a handler that sleeps 3 s   -> exit 28
port with no listener                        -> exit 7  (connection refused)
http://nonexistent.invalid/                  -> exit 6  (could not resolve)
--connect-timeout 1 to 203.0.113.1:81        -> exit 28
server closes after 10 of 100 bytes          -> exit 18 (transfer closed with 90 bytes remaining)
```

Exit 28 appears twice: the first connected and waited, the second never connected. That address is a documentation range. Refused (7) is fast and means a closed port; a timeout means packets vanish, for example a firewall or a dead host. Use `-sS`, or `-s` hides the error message.

## Redirects, Host and compression

Without `-L` curl prints the 301 and stops. With it, `-w` counts the chain:

```
$ curl -s -o /dev/null -L -w 'redirects=%{num_redirects} final=%{url_effective} code=%{http_code}\n' .../old
redirects=2 final=http://127.0.0.1:18080/ok code=200
```

That was a 301 then a 302: a {{< term "http-redirect" "redirect" >}} chain. To test a virtual host before DNS exists, pin the name: `--resolve shop.example.test:18080:127.0.0.1` made the server see `Host: shop.example.test:18080`, and `-H 'Host: api.example.test'` made it see exactly that. A gzip response printed as bytes starting `1f 8b` until I added `--compressed`.

## dig: ask a named resolver

Always name the resolver (`@1.1.1.1`) so you know who answers. These are public answers from a {{< term "recursive-resolver" "recursive resolver" >}}:

```
$ dig @1.1.1.1 example.com NS +short
hera.ns.cloudflare.com.
elliott.ns.cloudflare.com.
$ dig @1.1.1.1 example.com MX +short
0 .
$ dig @1.1.1.1 example.com TXT +short
"v=spf1 -all"
```

The MX `0 .` is a "null MX": the domain accepts no mail. A second TXT record was a token I left out. The {{< term "ttl" "TTL" >}} column is the second number of an answer line. I queried the same name three times, a few seconds apart, and got 71, 96 and 80. It did not count down steadily; my guess is that several caches sit behind one resolver address, but I did not verify that.

A name that does not exist gives {{< term "nxdomain" "NXDOMAIN" >}}:

```
$ dig @1.1.1.1 nonexistent.invalid A
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
;; AUTHORITY SECTION:
.   86400 IN SOA a.root-servers.net. nstld.verisign-grs.com. ...
```

`+trace` walks from the root. Trimmed to server names, my run went root server (`i.root-servers.net`), then a `.com` server (`l.gtld-servers.net`), then an authoritative server (`elliott.ns.cloudflare.com`), which gave the final A record.

## Ports and path

```
$ nc -zv 127.0.0.1 18080
Connection to 127.0.0.1 port 18080 [tcp/*] succeeded!
$ nc -zv 127.0.0.1 18999
nc: connectx to 127.0.0.1 port 18999 (tcp) failed: Connection refused
$ lsof -nP -iTCP:18080 -sTCP:LISTEN     (only my line kept)
srv  IPv4  TCP  127.0.0.1:18080 (LISTEN)
```

{{< term "traceroute" "traceroute" >}} sends packets with a growing {{< term "ttl" "TTL" >}}; each router that drops one answers with {{< term "icmp" "ICMP" >}}. Against {{< term "loopback" "loopback" >}} it has one hop:

```
$ traceroute -m 3 127.0.0.1
 1  localhost (127.0.0.1)  <ms values omitted>
```

On the internet it prints one line per hop; a hop showing `* * *` often only means that router does not answer, not that the path is broken.

## A layered checklist

| Layer | Command | Failure looks like |
|---|---|---|
| Name | `dig @1.1.1.1 name +short` | empty, NXDOMAIN; curl exit 6 |
| Route | `traceroute host` | `* * *` to the end |
| Port | `nc -zv host port` | refused (fast) or timeout (slow) |
| TLS | `openssl s_client` | handshake error |
| HTTP | `curl -sS -I url` | 4xx or 5xx, wrong redirect |
| App | logs, `lsof` | listener missing |

For TLS I used openssl in [TLS and certificates with openssl](/posts/net-tls-openssl/). I did not use curl for any certificate claim: this curl is built on SecureTransport and its verification behaved oddly in earlier runs.

## A few things to watch

- A 404 is not a network problem; check the exit code and the status separately.
- Pin names with `--resolve` instead of editing system files.
- Refused and timeout point to different causes; do not mix them.
- Always say which resolver you asked.

## Exercise

Add a handler that redirects forever. What does curl `-L` do, and which exit code and message appear? Then look up `--max-redirs`.

## What's next

The next post is "Case study: why is this request slow".
