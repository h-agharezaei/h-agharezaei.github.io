+++
date = '2027-04-08T10:00:00+03:30'
draft = false
title = 'Layer 4 and layer 7 load balancers'
description = 'Layer 4 vs layer 7 load balancers in Go on loopback: per-connection vs per-request balancing, routing, hashing, health checks, least connections.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "load-balancer", "reverse-proxy", "http", "go", "health-check"]
cover = { image = "/images/covers/net-load-balancer-l4-l7.png", alt = "Layer 4 and layer 7 load balancers", hiddenInSingle = true }
+++

In [the previous post](/posts/net-grpc-over-http2/) one HTTP/2 connection carried 71 calls. That is great for efficiency and awkward for a {{< term "load-balancer" "load balancer" >}}: if the balancer only sees connections, all 71 calls go to one server. Here I build both kinds in Go, a layer 4 proxy and a layer 7 one, and count where requests land. See also [the TCP/IP model](/posts/net-tcp-ip-model/).

> Everything ran on `127.0.0.1` with random ports (not printed), Go 1.26, macOS, standard library only. The machine was busy, so I publish counts, not timings. I did not run nginx, HAProxy, Envoy or any cloud load balancer; this is about the ideas.

## Layer 4: balance connections

The L4 proxy accepts a {{< term "tcp" "TCP" >}} connection, dials the next backend in round-robin order and copies bytes both ways with `io.Copy`. It never parses HTTP. Three backends, each answering with its name. First 30 clients that open a new connection each, then one client with {{< term "keep-alive" "keep-alive" >}} sending 30 requests:

```
L4, 30 new connections:    b0=10 b1=10 b2=10 | proxy accepted 30
L4, 1 keep-alive conn x30: b0=30 | proxy accepted 1
```

That is the pitfall. The choice is made once per connection, so one long-lived client pins all its traffic to one backend. gRPC and any HTTP/2 client behave like the second line.

## Layer 7: balance requests

The L7 proxy is `httputil.ReverseProxy`, a {{< term "reverse-proxy" "reverse proxy" >}}. It terminates the client connection, reads each request and makes a new one to a backend picked per request. Same test, one client connection, 30 requests:

```
L7, 1 client conn x30: b0=10 b1=10 b2=10 | proxy accepted 1
```

One client connection, three backends. Because it parses the request, it can also edit it. My `Rewrite` function calls `SetXForwarded()` and sets `X-Request-ID`; the backend saw:

```
b2|/|xff=127.0.0.1|rid=req-0030
```

`X-Forwarded-For` is the client address, here loopback only. A real backend should trust it only when it comes from your own proxy, otherwise clients can forge it.

Routing by path: `/api/` went to a pool of b0 and b1, `/static/` to b2. With 10 requests of each:

```
path routing: api->b0=5 api->b1=5 static->b2=10
```

## Sticky routing and consistent hashing

To keep a user on one backend I hashed the `X-User` header modulo the number of backends:

```
X-User=ada -> b1    X-User=bob -> b2    X-User=cy -> b1
```

(Repeated requests gave the same answers.) The weakness is changing the pool. I took 10,000 keys, removed one of three backends and counted the keys whose backend changed. With `hash % N` and with a ring of 100 points per node ({{< term "consistent-hashing" "consistent hashing" >}}):

```
mod-N                    remapped 6672 of 10000 keys (3335 of them did not live on b1)
ring (100 points/node)   remapped 2302 of 10000 keys (0 of them did not live on b1)
```

With mod-N, a third of the keys that were fine moved anyway, which means lost sessions or cold caches. The ring moved only the removed node's keys. Exact counts depend on my FNV hash and key names.

## Health checks

I stopped one of three backends and sent 30 requests through a round-robin L7 proxy, in three setups:

```
no detection:    failed 10 of 30
passive (mark down on first transport error): failed 1 of 30
active (2 failed probes -> down): failed 0 of 30 after removal; b0=15 b2=15
```

Passive means the proxy learns from real failures: one request paid for the lesson. Active means a {{< term "health-check" "health check" >}} probes `/healthz` every 20 ms and removes a backend after 2 failures; I waited until it was removed, so no user request failed. Active checks cost extra traffic and can lag; passive ones need real failures. Production systems usually combine them and add retries for {{< term "idempotency" "idempotent" >}} requests. I did not add retries here.

## Algorithms: round robin, least connections

Round robin ignores load. I made b0 slow (100 ms per request) and sent 60 requests with 6 concurrent workers:

```
rr: b0(slow)=20 b1=20 b2=20
lc: b0(slow)=2 b1=35 b2=23
```

Least connections picks the backend with the fewest in-flight requests, so the slow one received 2. The split between b1 and b2 varies from run to run. A third idea, "power of two random choices" (pick two at random, take the less loaded), I only mention; I did not run it.

## L4 or L7?

L7 can route by path or header, edit headers, retry, spread HTTP/2 requests and terminate {{< term "tls" "TLS" >}}. It pays for that: it must buffer and parse, it holds the private key, and it is one more thing that understands your protocol. L4 is simpler and protocol-agnostic. With TLS passthrough an L4 balancer forwards encrypted bytes and cannot see paths; with termination an L7 balancer decrypts and often re-encrypts to the backend. I only describe this here; certificates are in [TLS and certificates with openssl](/posts/net-tls-openssl/).

## A few things to watch

- With L4, a long-lived connection (HTTP/2, gRPC, WebSocket) sticks to one backend; use L7 balancing for those.
- Trust `X-Forwarded-For` only from your own proxies.
- Detect failure both actively and passively, and keep retries to idempotent requests.
- `hash % N` reshuffles almost everything when N changes.

## Exercise

Add `lc` mode with a backend that is slow only for `/report`. Does connection count still reflect load? What would you track instead?

## What's next

The next post is "Network troubleshooting with curl, dig and traceroute".
