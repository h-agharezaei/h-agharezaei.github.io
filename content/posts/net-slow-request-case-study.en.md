+++
date = '2027-04-23T10:00:00+03:30'
draft = false
title = 'Case study: why is this request slow'
description = 'Why is this request slow: a Go httptrace phase breakdown of four mystery requests on loopback, plus curl timings and a layered checklist.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "latency", "troubleshooting", "httptrace", "curl", "case-study"]
cover = { image = "/images/covers/net-slow-request-case-study.png", alt = "Case study: why is this request slow", hiddenInSingle = true }
+++

In [the previous post](/posts/net-troubleshooting-curl-traceroute/) we built a toolbox. This last post of the series uses it on one question every backend engineer gets: "this request is slow, why?" The trick is to stop looking at the total and split it into phases: name lookup, {{< term "tcp" "TCP" >}} connect, {{< term "tls" "TLS" >}} handshake, waiting for the first byte ({{< term "ttfb" "TTFB" >}}), body download. See also [the TCP/IP model](/posts/net-tcp-ip-model/) and [DNS in practice](/posts/net-dns-in-practice/).

> Privacy: everything ran on `127.0.0.1` with a self-signed certificate for `localhost` (the client skips verification, fine only for this local demo). The machine was very busy (load average above 20), so numbers are rounded to 50 ms: the injected delays (300-400 ms) dominate. I did not test real DNS, real ISP latency, packet loss or packet captures.

## The setup

A small Go program (a local example, no repo) has a server and a client. The server can inject a delay in each phase: a listener that sleeps after `Accept`, a TLS `GetCertificate` that sleeps, a handler that sleeps before headers (`?h=400`), a body that trickles (`?b=3&bd=100`), and a big body written slowly (`?big=15`). The client uses `net/http/httptrace`. The "name resolution" delay is a sleep inside `DialContext`: it simulates a slow lookup and is not real DNS.

## Four mystery requests

Output of the client, in ms (rounded to 50), for each request:

```
baseline  dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 1 dns=300 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 2 dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 3 dns=  0 connect=  0 tls=  0 wait=  0 ttfb=400 body=  0  bytes=3
mystery 4 dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=300  bytes=30
```

In 1 the time is before any socket exists: the client is waiting for a name. In 2 the TCP connect is instant but the handshake is slow: the server's TLS layer is busy. In 3 everything is fast until the request was written, then 400 ms of silence: the handler is slow, not the network. In 4 the headers came quickly but 30 bytes took 300 ms: that is a trickle, not bandwidth. Compare with a throttled big response:

```
big       ... ttfb=  0 body=300  bytes=245760
```

Same 300 ms, but 245,760 bytes. Bytes tell you whether the body is slow or just large.

curl shows the same story with `-w`; its variables are cumulative:

```
$ curl -sk -o /dev/null -w 'connect=%{time_connect} tls_done=%{time_appconnect} first_byte=%{time_starttransfer} total=%{time_total}\n' https://localhost:18102/
connect=0.000307 tls_done=0.327153 first_byte=0.327520 total=0.327621
```

For the handler case first_byte was 0.41 s while tls_done was 0.013 s, and for the trickle total was 0.306 s against first_byte 0.0036 s. curl cannot see my simulated DNS delay; it did its own lookup. Its baseline tls_done was 0.078 s, which I put down to the busy machine.

## A trap: the delayed accept

With the server sleeping after `Accept`:

```
accept    dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0
```

The kernel finishes the TCP handshake before the program calls accept, so the delay shows up as a slow TLS handshake. From the client alone, slow `GetCertificate` and a stalled accept loop are indistinguishable. You need server-side data to tell them apart.

## Reuse, pools and HTTP/2

With {{< term "keep-alive" "keep-alive" >}} the second request skips the early phases. Two requests, simulated 300 ms lookup, 100 ms handler:

```
request 1: dns=300 ... ttfb=100 reused=false
request 2: dns=  0 ... ttfb=100 reused=true
```

`GotConn.Reused` was `true` and the lookup, connect and TLS cost vanished. Pool exhaustion looks like waiting before connect. With `MaxConnsPerHost=1`, three concurrent requests to a 200 ms handler:

```
HTTP/1.1  req 0: wait=  0  done at 200
          req 1: wait=200  done at 400
          req 2: wait=400  done at 600
HTTP/2    all three: wait=0  done at 200
```

Nothing is slow on the wire; requests queue for the {{< term "connection-pool" "connection pool" >}}. Compare the database case in [Connection pooling and its failure modes](/posts/db-connection-pooling/) and the HTTP client in [Building an API with net/http in Go](/posts/go-http-api-stdlib/). With HTTP/2 the three requests shared one connection ({{< term "multiplexing" "multiplexing" >}}, see [HTTP/2 and what changes](/posts/net-http2/)). Retries can also hide latency (one slow request that was really two); I did not run that case.

## The layered elimination method

| Order | Layer | Phase that grows | First question |
|---|---|---|---|
| 1 | client | wait before dns | pool exhausted, CPU busy? |
| 2 | DNS | dns | which resolver answered? |
| 3 | connect | connect | refused, timeout, far away? |
| 4 | TLS | tls | cert chain, accept queue? |
| 5 | server queue | tls or ttfb | threads, backlog full? |
| 6 | handler | ttfb | slow query, lock, upstream? |
| 7 | body | body | bytes or trickle? |
| 8 | client again | after body | parsing? |

## A few things to watch

- Measure the phases of one request before guessing; the total hides the culprit.
- A big body and a trickling body both show a long download; check the bytes.
- Client-only numbers cannot separate a slow handshake from an accept stall.

## Exercise

Add a server flag that closes the connection after the headers. What error does the client report? Then add a retry and decide how you would notice the hidden second attempt.

## What's next

The Networking series ends here. Continue with the Linux series and the Distributed Systems series.
