+++
date = '2027-04-23T10:00:00+03:30'
draft = false
title = 'Case study: why is this request slow'
description = 'Why is this request slow: a Go httptrace phase breakdown of four mystery requests on loopback, plus curl timings and a layered checklist.'
contentType = 'analysis'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "latency", "troubleshooting", "httptrace", "curl", "case-study"]
cover = { image = "/images/covers/net-slow-request-case-study.png", alt = "Case study: why is this request slow", hiddenInSingle = true }
+++

"This request is slow. Why?" Every backend engineer gets this question, and the usual first answer is a number, for example 800 ms. That number does not help, in the same way that "your parcel took five days" does not help. You need the tracking events: when it left the warehouse, when it cleared customs, when the courier picked it up. A request has tracking events too, and the whole skill is to stop looking at the total and look at them.

The events of an HTTPS request are: looking up the name ({{< term "dns" "DNS" >}}), opening the {{< term "tcp" "TCP" >}} connection, the {{< term "tls" "TLS" >}} handshake, the wait for the first byte of the answer ({{< term "ttfb" "TTFB" >}}, "time to first byte"), and downloading the body. If one of them is slow, the total is slow, and which one it is tells you whom to call: the DNS provider, the network, the certificate setup, the application, or nobody, because the answer is just large. This post uses the tools from [the previous post](/posts/net-troubleshooting-curl-traceroute/) to do this on a small lab, and it is the last post of the Networking series. See also [the TCP/IP model and the path of a packet](/posts/net-tcp-ip-model/) and [DNS in practice](/posts/net-dns-in-practice/).

> Setup: everything ran on `127.0.0.1` with a random port, macOS (Darwin arm64), Go 1.27.3, curl 8.7.1, and a self-signed certificate for `localhost` made inside the demo (the client skips verification, which is fine only for this local demo). The demo was first written with Go 1.26. This is a **lab, not a real incident**: I injected every delay myself, so I know the right answers in advance, and the question is whether the measurement points to them. Loopback timings are not Internet timings. When I re-ran it the machine's load average was between 3 and 6, higher than I like for timing numbers. So the client numbers are rounded to 50 ms (the injected delays of 300 to 400 ms dominate), and the curl numbers below are raw and noisy: read the pattern, not the digits. The rounded output was identical to the one from the original run, when the machine was even busier. I did not test real DNS, real ISP latency, packet loss or packet captures.

## The lab

The demo is one small Go program (a local example, no repository). It has a server and a client.

The server can inject a delay into any phase, one at a time:

- a listener that sleeps after `Accept` (`-accept`);
- a TLS `GetCertificate` function that sleeps (`-tls`), which delays the handshake;
- a handler that sleeps before it writes any header (`?h=400`);
- a body that trickles, 10 bytes at a time with a pause between pieces (`?b=3&bd=100`);
- a big body written slowly in 16 KiB pieces (`?big=15`).

The client uses Go's `net/http/httptrace` package, which calls your functions at each event of a request (got a connection, TLS started, TLS finished, request written, first byte received). From the timestamps it prints six numbers, each in milliseconds and rounded to 50: `dns`, `connect`, `tls`, `wait` (waiting for a free connection from the pool, before anything is dialed), `ttfb` (from the moment the request was written to the first byte of the answer), and `body` (from the first byte to the end). One honest caveat: the "name resolution" delay is only a `sleep` inside the client's dial function. It simulates a slow lookup and is not real DNS.

## A baseline first

Before investigating anything, measure a healthy request. The server has no delays here:

```
dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
```

Everything is under 25 ms (so it rounds to 0), three bytes arrived (`ok\n`), and it was a new connection (`reused=false`). Now the mysteries.

## Four mystery requests

Each of the next four requests is slow, and each is slow for a different reason. I show only the output. Try to guess the cause from it before reading on.

```
dns=300 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
dns=  0 connect=  0 tls=  0 wait=  0 ttfb=400 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=300 ms  bytes=30 reused=false HTTP/1.1 200 OK
```

Here is how I would read them, one by one.

1. **`dns=300`.** The time is spent before any socket exists. The client is waiting for a name to become an address. Nothing about the network or the server can be blamed yet: look at the resolver. (In the lab, I injected this with a 300 ms sleep in the dial function.)
2. **`tls=300`.** The TCP connection was instant (`connect=0`) but the handshake took 300 ms. The server's TLS layer is slow to answer, or busy. The injected cause: `GetCertificate` slept for 300 ms.
3. **`ttfb=400`.** Everything is fast until the request was written, then 400 ms of silence. The connection and the handshake are fine. The server received the request and thought for 400 ms before saying anything: the handler is slow, and it is not a network problem. The injected cause: `?h=400`.
4. **`body=300`, `bytes=30`.** The headers came quickly, but 30 bytes took 300 ms. That is not a bandwidth problem. Thirty bytes cannot be large; the body trickles, three pieces with a 100 ms pause. The injected cause: `?b=3&bd=100`.

In each case one phase carries the delay and the others are zero, so the phase names the suspect. Now compare case 4 with a throttled **large** response:

```
dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=300 ms  bytes=245760 reused=false HTTP/1.1 200 OK
```

The same 300 ms of `body`, but 245,760 bytes (15 pieces of 16 KiB, each written, then a 20 ms pause). A long download is not the same as a slow download. The byte count says whether the body is slow because it is big or slow because the server stalls between pieces. Without the bytes you could not tell cases 4 and this one apart.

## What curl sees

curl can measure the same phases from outside, with `-w`. Its variables are cumulative: each time is counted from the start of the transfer, so the time of a phase is the difference between two numbers. Four runs: slow TLS, slow handler, trickling body, and a healthy baseline:

```
$ curl -sk -o /dev/null -w 'connect=%{time_connect} tls_done=%{time_appconnect} first_byte=%{time_starttransfer} total=%{time_total}\n' https://127.0.0.1:PORT/...
connect=0.000343 tls_done=0.378337 first_byte=0.378910 total=0.379055     (slow TLS)
connect=0.000359 tls_done=0.004378 first_byte=0.407458 total=0.407849     (slow handler, ?h=400)
connect=0.000491 tls_done=0.004823 first_byte=0.005215 total=0.310811     (trickling body)
connect=0.000469 tls_done=0.004856 first_byte=0.005240 total=0.005353     (baseline)
```

The jumps tell the story. In the first line `tls_done` jumps to 0.378 s, and nothing after that costs time. In the second, `tls_done` is 0.004 s but `first_byte` is 0.407 s: the wait is after the handshake. In the third, the first byte arrives at 0.005 s and the total is 0.311 s: the time is in the body. The slow-TLS number (0.378 s for an injected 300 ms) is higher than the rest because the machine was busy; I take the pattern, not the digits. curl cannot see my simulated DNS delay: that delay lives inside my Go client, and curl was given an IP address, so it did no lookup at all.

## A trap: the delayed accept

Here is a case where the client's picture misleads. I started the server with a delay *after* `Accept`, so the server program accepts connections slowly, and a normal fast TLS setup:

```
dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
```

The client shows `connect=0` and `tls=300`, the same as in case 2. The reason: the operating system completes the TCP handshake on its own, before the program calls `accept`. So the connect looks instant, and the delay appears as a slow TLS handshake, because the TLS hello is waiting in the queue. From the client alone, a slow `GetCertificate` and a stalled accept loop are indistinguishable. You need data from the server side to tell them apart: logs, or how many connections are waiting in the listen queue (see [TCP: the handshake and connection states](/posts/net-tcp-handshake-states/)).

## Reuse, pools and HTTP/2

The early phases only matter for new connections. With {{< term "keep-alive" "keep-alive" >}} the second request over the same connection skips them. I made two requests in a row with the simulated 300 ms lookup and a 100 ms handler:

```
request 1: dns=300 connect=  0 tls=  0 wait=  0 ttfb=100 body=  0 ms  bytes=3 reused=false HTTP/1.1 200 OK
request 2: dns=  0 connect=  0 tls=  0 wait=  0 ttfb=100 body=  0 ms  bytes=3 reused=true HTTP/1.1 200 OK
```

The second one has `reused=true`, which comes from `GotConn.Reused`, and the lookup (and the connect and TLS costs) vanished. Only the handler's 100 ms is left. This is why "the first request is always slow" is so common.

A different problem looks like a slow request but is not on the wire at all: waiting for a connection from the pool. I limited the client to `MaxConnsPerHost=1` and sent three requests together to a handler that takes 200 ms. `wait` is the time before a connection was available, and `done at` is the time since the start:

```
HTTP/1.1:
req 0: wait=  0 ms  done at 200 ms  reused=false HTTP/1.1 200 OK
req 1: wait=200 ms  done at 400 ms  reused=true HTTP/1.1 200 OK
req 2: wait=400 ms  done at 600 ms  reused=true HTTP/1.1 200 OK
HTTP/2:
req 0: wait=  0 ms  done at 200 ms  reused=false HTTP/2.0 200 OK
req 1: wait=  0 ms  done at 200 ms  reused=true HTTP/2.0 200 OK
req 2: wait=  0 ms  done at 200 ms  reused=true HTTP/2.0 200 OK
```

With HTTP/1.1, one connection serves one request at a time. The second request waited 200 ms for the first to finish, and the third waited 400 ms. Nothing is slow in the network or in the server: the requests queue for the {{< term "connection-pool" "connection pool" >}}. With HTTP/2 the three requests shared one connection at the same time ({{< term "multiplexing" "multiplexing" >}}, see [HTTP/2 and what changes](/posts/net-http2/)), so all three finished at 200 ms. The database version of the same problem is in [Connection pooling and its failure modes](/posts/db-connection-pooling/), and the HTTP client side is in [Building an API with net/http in Go](/posts/go-http-api-stdlib/). A related trap is retries: a client that silently retries can turn one slow request into two, and it looks like one long request. I did not run that case.

## The layered elimination method

The four mysteries suggest an order for investigating. Start at the client's side and move toward the server; at each step ask what would make that phase grow:

| Order | Layer | Phase that grows | First question |
|---|---|---|---|
| 1 | client | wait before dns | is the pool exhausted, is the CPU busy? |
| 2 | DNS | dns | which resolver answered? (simulated in the lab) |
| 3 | connect | connect | refused, timeout, far away? |
| 4 | TLS | tls | certificate chain, accept queue? |
| 5 | server queue | tls or ttfb | threads, is the backlog full? |
| 6 | handler | ttfb | slow query, lock, upstream? |
| 7 | body | body | big, or trickling? |
| 8 | client again | after body | parsing? |

The table repeats the lessons above: pool waits show up before everything else, a slow handler is a long `ttfb`, and the byte count separates a big body from a trickling one. Rows 4 and 5 can look identical from the client, which is the delayed-accept trap. This list is not a law. It is the order I would check things in, and the lab covers rows 1, 2, 4, 5, 6 and 7. I did not build rows 3 and 8.

## What the four requests taught

- Measure the phases of one request before guessing. The total hides the culprit.
- A big body and a trickling body both show a long download. Check the byte count before you blame the network.
- Numbers from the client alone cannot separate a slow handshake from a stalled accept loop. Get a number from the server too.

## What's next

The Networking series ends here. Two series continue the blog: the Linux series, and the Distributed Systems series.
