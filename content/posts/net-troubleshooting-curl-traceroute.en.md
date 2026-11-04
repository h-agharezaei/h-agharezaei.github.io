+++
date = '2027-04-16T10:00:00+03:30'
draft = false
title = 'Network troubleshooting with curl, dig and traceroute'
seoTitle = 'Network troubleshooting with curl, dig, traceroute'
description = 'Network troubleshooting with curl, dig and traceroute: real exit codes, redirects, Host header, DNS answers, NXDOMAIN and a layer-by-layer checklist.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "troubleshooting", "curl", "dig", "traceroute", "dns"]
cover = { image = "/images/covers/net-troubleshooting-curl-traceroute.png", alt = "Network troubleshooting with curl, dig and traceroute", hiddenInSingle = true }
+++

"The request hangs." That sentence can mean five different things, and each one needs a different fix. Maybe the name never turned into an address. Maybe the address was found but nothing answered. Maybe the connection opened and the server went quiet. Or the server answered with an error, which is a perfectly healthy network doing its job. Staring at the application logs does not tell you which of these it is.

The idea of this post is simple: a request climbs a ladder, and it can fall off at any rung. First the name is looked up ({{< term "dns" "DNS" >}}), then a {{< term "tcp" "TCP" >}} connection is opened, then (for https) the {{< term "tls" "TLS" >}} handshake happens, then the {{< term "http" "HTTP" >}} request is answered, and finally the application does its work. Troubleshooting means finding the lowest rung that fails. Every rung has a tool: `dig` for names, `nc` for ports, `openssl` for TLS, `curl` for HTTP, and `traceroute` for the path. And `curl` is special, because its **exit code** already tells you which rung it fell from.

Every box added to the path, like the balancer in [the previous post](/posts/net-load-balancer-l4-l7/), is one more suspect. Here I go through the ladder with real commands. It builds on [the TCP/IP model and the path of a packet](/posts/net-tcp-ip-model/), [DNS in practice](/posts/net-dns-in-practice/) and [HTTP/1.1 by hand](/posts/net-http1-by-hand/).

> Privacy and setup: macOS (Darwin arm64), curl 8.7.1 (the first line of `curl --version` is `curl 8.7.1 (x86_64-apple-darwin26.0) libcurl/8.7.1 (SecureTransport) LibreSSL/3.3.6 zlib/1.2.12 nghttp2/1.69.0`), DiG 9.10.6. The servers ran on `127.0.0.1` with a random free port, which I write as `PORT` below (the commands use `$B` for `http://127.0.0.1:$PORT`). The test server is a small Go program with one handler for each situation (`/ok`, `/missing`, `/boom`, `/slow`, `/old`, `/host`, `/gzip`, `/early`). For DNS I asked the public resolver `1.1.1.1` and only about `example.com` and a name that does not exist. I did not paste any `traceroute` through the internet, because it lists the real routers of my network; I explain the output and use an invented example instead. I show no timings here (the machine was busy). `ss` and `ip` are Linux tools and I did not run them.

## The top rungs: what did the server say?

I start at the top, because HTTP is where most problems turn out to be. `curl -v` prints the whole conversation. Lines starting with `>` are what curl sent, lines starting with `<` are what the server sent back, and lines starting with `*` are curl's own comments:

```
$ curl -sv $B/ok
*   Trying 127.0.0.1:PORT...
* Connected to 127.0.0.1 (127.0.0.1) port PORT
> GET /ok HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
>
* Request completely sent off
< HTTP/1.1 200 OK
< Date: Wed, 04 Nov 2026 16:49:55 GMT
< Content-Length: 3
< Content-Type: text/plain; charset=utf-8
<
{ [3 bytes data]
* Connection #0 to host 127.0.0.1 left intact
ok
```

Read it as the ladder. "Trying" and "Connected" are the TCP rung: curl found the address and the connection opened. The `>` lines are the request, including the `Host` header curl added. The `<` lines are the answer: status 200 and three bytes of body, `ok`. If you only want the headers there is `-I`, which sends a `HEAD` request. If you want facts about the transfer there is `-w`, which prints a format string after the transfer. Let me ask for the status of a page that does not exist, and of one that crashes:

```
$ curl -s -o /dev/null -w 'http=%{http_code}\n' $B/missing
http=404
$ curl -s -o /dev/null -w 'http=%{http_code}\n' $B/boom
http=500
```

(`-o /dev/null` throws the body away; `-s` hides the progress meter.) Both exited with code 0. This is the first thing to learn: a 404 or a 500 is an *answer*, so from curl's point of view the transfer worked. HTTP status and transport errors are separate things. If the page says 500, look at the server, not at the network.

## The bottom rungs: when there is no answer

When curl cannot even get an answer, the exit code is the signal. I ran each of these cases:

```
--max-time 1 on a handler that sleeps 3 s   -> exit 28
port with no listener                        -> exit 7  (connection refused)
http://nonexistent.invalid/                  -> exit 6  (could not resolve)
--connect-timeout 1 to 203.0.113.1:81        -> exit 28
server closes after 10 of 100 bytes          -> exit 18 (transfer closed with 90 bytes remaining)
```

Here are the real messages for three of them (use `-sS`: `-s` alone hides the error message, `-S` brings it back):

```
curl: (28) Operation timed out after 1011 milliseconds with 0 bytes received
curl: (7) Failed to connect to 127.0.0.1 port PORT2 after 0 ms: Couldn't connect to server
curl: (6) Could not resolve host: nonexistent.invalid
```

What each tells you:

- **Exit 6** is the name rung. The name did not turn into an address, so no packet was ever sent to the server. `.invalid` is a name reserved to never exist, which makes it a safe test.
- **Exit 7** is the connect rung, and it failed quickly. The machine answered, and said that no program listens on that port. This is "connection refused": a reset packet came back right away.
- **Exit 28** is a timeout and appears twice with different meanings. In the first line curl connected, sent the request and waited for a handler that sleeps. In the fourth it never connected: `203.0.113.1` is an address from a documentation range, so the SYN goes nowhere and no answer ever comes. A timeout without any answer means packets vanish, for example at a firewall or at a machine that is down. Refused is fast and means "closed"; a timeout is slow and means "silence". They point to different problems.
- **Exit 18** means the server promised 100 bytes in `Content-Length` and closed the connection after 10. The transfer was cut in the middle, a failure on the HTTP rung that looks like a network problem.

## Redirects, Host and compression

Three HTTP details cause confusion that looks like network trouble. First, redirects. Without `-L`, curl shows the redirect and stops. With `-L` it follows, and `-w` can count the hops:

```
$ curl -s -o /dev/null -w 'code=%{http_code} redirect_url=%{redirect_url}\n' $B/old
code=301 redirect_url=http://127.0.0.1:PORT/mid
$ curl -s -o /dev/null -L -w 'redirects=%{num_redirects} final=%{url_effective} code=%{http_code}\n' $B/old
redirects=2 final=http://127.0.0.1:PORT/ok code=200
```

The first command stops at the 301 and tells where it points. The second follows two hops and ends at `/ok`. With `-v` you can see the two extra requests: `/old` answers 301 with `Location: /mid`, `/mid` answers 302 with `Location: /ok`, and `/ok` answers 200. That is a {{< term "http-redirect" "redirect" >}} chain.

Second, the `Host` header. A server with several sites, or a proxy, decides who you are talking to by the `Host` header, not by the IP address. To test a site before its DNS record exists, you can pin a name to an address with `--resolve`, or just set the header with `-H`. The `/host` handler prints the header it received:

```
$ curl -s $B/host
Host header seen: 127.0.0.1:PORT
$ curl -s --resolve shop.example.test:PORT:127.0.0.1 http://shop.example.test:PORT/host
Host header seen: shop.example.test:PORT
$ curl -s -H 'Host: api.example.test' $B/host
Host header seen: api.example.test
```

In the second command curl connected to `127.0.0.1` but behaved as if `shop.example.test` had resolved to it. This is cleaner than editing a system hosts file.

Third, compression. A server may send a gzip body when the client says it accepts it. If you see odd bytes, check this. My `/gzip` handler always compresses:

```
$ curl -s $B/gzip | xxd | head -2
00000000: 1f8b 0800 0000 0000 00ff 0011 00ee ff63  ...............c
00000010: 6f6d 7072 6573 7365 6420 6865 6c6c 6f0a  ompressed hello.
$ curl -s --compressed $B/gzip
compressed hello
```

The bytes `1f 8b` at the start are the signature of a gzip stream. With `--compressed` curl asks for compression and decodes it for you.

## dig: ask a named resolver

For the name rung, `dig` shows what DNS really answers. Always name the resolver you ask (the part after `@`), so you know who gave the answer. These queries go to the public resolver `1.1.1.1`, a {{< term "recursive-resolver" "recursive resolver" >}} that does the lookup for you, and only ask about `example.com`:

```
$ dig @1.1.1.1 example.com NS +short
hera.ns.cloudflare.com.
elliott.ns.cloudflare.com.
$ dig @1.1.1.1 example.com MX +short
0 .
$ dig @1.1.1.1 example.com TXT +short
"v=spf1 -all"
"_k2n1y4vw3qtb4skdx9e7dxt97qrmmq9"
```

`NS` shows which servers are in charge of the domain. The MX answer `0 .` is a "null MX": the domain says it accepts no mail. The TXT answer has an SPF policy (`-all` means "no server may send mail for this domain") and a verification token. The answers of public DNS can change over time, so yours may differ.

One practical note. The first time I ran these queries with `+time=3 +tries=1`, the NS, MX and A queries printed `connection timed out; no servers could be reached` and only the TXT query worked. Running again with `+time=4 +tries=3` gave full answers. A timeout from `dig` is the same "silence" as a curl timeout: it does not mean the name does not exist.

The {{< term "ttl" "TTL" >}} is the second column of an answer line, the number of seconds a cache may keep the answer. I asked for the same TXT record three times, three seconds apart, and got `300`, `300` and `62`. It did not count down steadily. My guess is that several caches sit behind one resolver address, but I did not verify that.

A name that does not exist gives {{< term "nxdomain" "NXDOMAIN" >}}, which is a real DNS answer, not a failure:

```
$ dig @1.1.1.1 nonexistent.invalid A
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 2216
;; flags: qr rd ra ad; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
...
;; AUTHORITY SECTION:
.			86400	IN	SOA	a.root-servers.net. nstld.verisign-grs.com. 2026110400 1800 900 604800 86400
```

I kept only the status line, the flags line and the authority section; I left out the lines that print the resolver address and the time of the query. `status: NXDOMAIN` is the part that matters. The `id` and the SOA serial number change over time.

`dig +trace` shows how the lookup would go without a helpful resolver, step by step from the root. For `example.com A`, the answers came from a root server (`j.root-servers.net` this time), then from a `.com` server (`k.gtld-servers.net`), then from one of the domain's own servers (`hera.ns.cloudflare.com`), which gave the final record. Which root and `.com` server answers can differ between runs.

## Ports and the path

For the connect rung without HTTP, `nc -z` just tries to open a connection and `-v` reports the result. `lsof` shows who listens on a port on this machine:

```
$ nc -zv 127.0.0.1 PORT
Connection to 127.0.0.1 port PORT [tcp/*] succeeded!
$ nc -zv 127.0.0.1 PORT2
nc: connectx to 127.0.0.1 port PORT2 (tcp) failed: Connection refused
$ lsof -nP -iTCP:PORT -sTCP:LISTEN     (only my line kept, columns reduced)
srv  IPv4  TCP  127.0.0.1:PORT (LISTEN)
```

`PORT` has my server and `PORT2` is a port where nothing listens. `lsof` shows my server, `srv`, as the one listening, so "is something listening, and which program?" is answered locally.

The last tool is {{< term "traceroute" "traceroute" >}}. It sends packets with a small TTL (time to live, a counter that every router decreases by one); the router that makes it reach zero drops the packet and answers with an {{< term "icmp" "ICMP" >}} message, so you learn its address. Then it raises the TTL by one and repeats, which reveals the path one router at a time. To the {{< term "loopback" "loopback" >}} address it has one hop:

```
$ traceroute -m 3 127.0.0.1
traceroute to 127.0.0.1 (127.0.0.1), 3 hops max, 40 byte packets
 1  localhost (127.0.0.1)  <three ms values omitted>
```

On the internet it prints one line per router, and that list is the real route from your network, which is exactly what I will not publish. So here is an **invented** example with addresses from the documentation ranges, only to show how to read it:

```
 1  192.0.2.1
 2  198.51.100.7
 3  * * *
 4  * * *
 5  203.0.113.9
```

A `* * *` line means no answer came for that hop. That is not automatically a break: many routers simply do not answer these probes, and the path can still work, as the answer of hop 5 shows. A path that shows `* * *` for every line from some hop to the end is more suspicious, but even that can be a firewall that drops probes.

## The ladder as a checklist

| Rung | Command | Failure looks like |
|---|---|---|
| Name | `dig @1.1.1.1 name +short` | empty answer, NXDOMAIN; curl exit 6 |
| Route | `traceroute host` | `* * *` all the way to the end |
| Port | `nc -zv host port` | refused (fast) or timeout (slow); curl exit 7 or 28 |
| TLS | `openssl s_client` | handshake error |
| HTTP | `curl -sS -I url` | 4xx or 5xx, wrong redirect |
| App | logs, `lsof` | listener missing |

Work from the top of the table to the bottom and stop at the first failure. For the TLS rung I used openssl in [TLS and certificates with openssl](/posts/net-tls-openssl/). I did not use curl for any certificate claim: this curl is built on SecureTransport, and its certificate checks behaved oddly in earlier runs.

I did not put timing numbers in this post. But `curl -w` can also print how long each rung took (`time_namelookup`, `time_connect`, `time_appconnect`, `time_starttransfer`, `time_total`). That is the tool the next post uses to find which rung is slow.

## Misreadings to avoid

- **Treating a 404 as a network problem.** Read the exit code and the HTTP status separately. A 404 or 500 is an answer; the network worked.
- **Editing system files to test a name.** `--resolve` pins a name for one command and changes nothing else on your machine.
- **Mixing up refused and timeout.** Refused is a quick "no" from a reachable machine, a timeout is silence. Chase them differently.
- **Forgetting to say which resolver you asked.** The same name can give different answers from different resolvers, and caches make that worse. Write `@resolver` in every `dig` you share.
- **Trusting `* * *` in traceroute.** Silent hops are normal. Judge the path by whether the destination answers.

## Exercise

Add a handler that redirects to itself forever. What does `curl -L` do, and which exit code and message appear? Then look up `--max-redirs` in the curl manual. I did not run this one.

## What's next

The next post is "Case study: why is this request slow". The ladder tells you which rung failed; when nothing fails but the request is slow, you need to measure how long each rung takes, and that is what the case study does.
