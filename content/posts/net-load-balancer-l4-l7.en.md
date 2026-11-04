+++
date = '2027-04-08T10:00:00+03:30'
draft = false
title = 'Layer 4 and layer 7 load balancers'
description = 'Layer 4 vs layer 7 load balancers in Go on loopback: per-connection vs per-request balancing, routing, hashing, health checks, least connections.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "load-balancer", "reverse-proxy", "http", "go", "health-check"]
cover = { image = "/images/covers/net-load-balancer-l4-l7.png", alt = "Layer 4 and layer 7 load balancers", hiddenInSingle = true }
+++

You put three copies of a service behind a {{< term "load-balancer" "load balancer" >}}, send traffic through it, and look at the dashboards. Two of the servers are idle and the third is on fire. The balancer is working as designed. It just made its decision at a different level than you assumed.

A load balancer is a program that sits in front of several identical servers (called backends) and decides which one gets each piece of work. The important question is what "a piece of work" means to it. Think of a receptionist at a building with three counters. One receptionist sends each person who walks in the door to the next free counter, and does not care what the person wants. Another one listens to every question and can send the first question to counter 1 and the second to counter 2, even from the same person. The first one works on **connections** (layer 4), the second one on **requests** (layer 7). The numbers count the layers of the seven-layer OSI model, which [The TCP/IP model and the path of a packet](/posts/net-tcp-ip-model/) introduced: layer 4 is the transport layer, where {{< term "tcp" "TCP" >}} lives, and layer 7 is the application layer, where HTTP lives.

The [previous post](/posts/net-grpc-over-http2/) ended with one HTTP/2 connection that carried 71 gRPC calls. That is where this question stops being theoretical: a balancer that only sees connections sees one connection and can only send all 71 calls to one backend. In this post I build both kinds of balancer in Go, a layer 4 proxy and a layer 7 proxy, and count where the requests land. For the architecture side (service discovery, client-side balancing) see [Service discovery and load balancing](/posts/ds-service-discovery-load-balancing/).

> Everything ran on `127.0.0.1` with random ports (not printed), macOS (Darwin arm64), Go 1.27.3, standard library only. The demo was first written with Go 1.26 and I re-ran it with 1.27.3 for this version. The machine was busy, so I publish counts, not timings. I did not run nginx, HAProxy, Envoy or any cloud load balancer; this post is about the ideas, not about those products.

## The test bed

The demo starts three small HTTP servers, `b0`, `b1` and `b2`. Each answers with its own name, so a client can tell who served it. A proxy listens in front of them, and a client sends requests to the proxy. I count how many requests each backend got. The same counting is used in every experiment below.

## Layer 4: balance connections

A layer 4 proxy does very little. It accepts a TCP connection, opens a second connection to the next backend in turn (this is round robin: b0, b1, b2, b0, ...), and copies bytes in both directions. It never reads the HTTP inside. This is the heart of it, trimmed from the demo (error handling and counters removed):

```go
c, _ := ln.Accept()                      // a client connected
b := backends[next % len(backends)]      // choose once, for this connection
up, _ := net.Dial("tcp", b.addr)         // connect to that backend
go io.Copy(up, c)                        // client -> backend
io.Copy(c, up)                           // backend -> client
```

The choice happens one time, on the line where `b` is picked. After that, every byte of this connection goes to the same backend. I tested it twice. First, 30 clients that each open a new connection for their one request. Second, one client that opens one connection and keeps it open ({{< term "keep-alive" "keep-alive" >}}), sending 30 requests on it:

```
L4, 30 new connections:    b0=10 b1=10 b2=10 | proxy accepted 30
L4, 1 keep-alive conn x30: b0=30 | proxy accepted 1
```

On the first line the load is perfectly even: 30 connections, 10 each. On the second line all 30 requests landed on `b0`, and the proxy accepted only one connection. This is the pitfall of layer 4. The balancer spreads connections, not work, so one long-lived client sends everything to one backend. gRPC, and any HTTP/2 client, behave like the second line, because they are designed to keep one connection open.

## Layer 7: balance requests

A layer 7 proxy understands HTTP. It accepts the client connection and reads each request. For each request it opens its own request to a backend, chosen again for every request. In Go this is `httputil.ReverseProxy`, a {{< term "reverse-proxy" "reverse proxy" >}}: a program that receives requests on behalf of the real servers and forwards them. The important parts of my setup:

```go
rp := &httputil.ReverseProxy{
    Rewrite: func(pr *httputil.ProxyRequest) {
        pr.SetURL(chosenBackend.u)   // chosen per request
        pr.SetXForwarded()           // add X-Forwarded-For and friends
        pr.Out.Header.Set("X-Request-ID", ...)
    },
}
```

The same test as before: one client connection, 30 requests.

```
L7, 1 client conn x30: b0=10 b1=10 b2=10 | proxy accepted 1
```

Still one connection from the client, but now the requests were spread evenly over three backends. The price is that the proxy must read and understand every request, and it is also a second HTTP client.

Because it parses the request, the proxy can change it, too. In my setup `Rewrite` adds an `X-Forwarded-For` header and an `X-Request-ID`. Here is the answer of the last backend, which prints what it saw:

```
b2|/|xff=127.0.0.1|rid=req-0030
```

The parts are the backend name, the path, the `X-Forwarded-For` value and the request id (the 30th request). `X-Forwarded-For` carries the address of the original client, because the backend only sees the proxy's address on its own connection. Here it is the loopback address, since the client was on this machine. A real backend should trust this header only when it comes from your own proxy. Otherwise any client can send a fake one.

The proxy can also route by what is in the request. I put two pools behind one proxy: `/api/` goes to b0 and b1, `/static/` goes to b2. With 10 requests of each kind:

```
path routing: api->b0=5 api->b1=5 static->b2=10
```

Layer 4 cannot do this at all. It never sees the path.

## Sticky routing and consistent hashing

Sometimes you want the same user to always reach the same backend, for example because a cache or a session lives there. The simplest rule is to compute a hash of something that identifies the user, take the remainder after dividing by the number of backends, and use that as the backend index. I did this with the `X-User` header:

```
  X-User=ada -> b1
  X-User=bob -> b2
  X-User=cy -> b1
  X-User=ada -> b1
  X-User=bob -> b2
  X-User=cy -> b1
  X-User=ada -> b1
```

The same name gives the same backend every time. The weakness appears when the number of backends changes. I took 10,000 keys, removed one of the three backends, and counted how many keys now map to a different backend. I did it with `hash % N` and with a **ring**, which is the idea of {{< term "consistent-hashing" "consistent hashing" >}}: place many points for every backend on a circle of hash values, hash each key onto the same circle, and give it to the first point you meet going around. Each backend got 100 points.

```
mod-N                    remapped 6672 of 10000 keys (3335 of them did not live on b1)
ring (100 points/node)   remapped 2302 of 10000 keys (0 of them did not live on b1)
```

Only the keys that lived on the removed backend must move. With `hash % N` the number of backends changed from 3 to 2, so almost every key got a new answer: 6672 moved, and 3335 of them were keys that did not live on the removed backend and had no reason to move. In a real system that means lost sessions or cold caches. With the ring, 2302 keys moved and none of them was an innocent one; those 2302 were the keys of the removed backend. (They are fewer than a third because 100 points per backend does not divide the ring perfectly evenly.) The exact counts depend on the FNV hash and on my key names, so expect other numbers with other choices, but the pattern is the point.

## Health checks

A balancer must stop sending traffic to a backend that is dead. I stopped one of the three backends and sent 30 requests through the round-robin layer 7 proxy, in three setups:

```
no detection:    failed 10 of 30
passive (mark down on first transport error): failed 1 of 30; b1 down = true
active (2 failed probes -> down): failed 0 of 30 after removal; b0=15 b2=15
```

- **No detection.** The proxy keeps choosing the dead backend one time in three: 10 of 30 requests failed.
- **Passive.** The proxy learns from real traffic. The first request to the dead backend fails, the proxy marks it down, and the others succeed. One user request paid for the lesson.
- **Active.** A separate loop sends a {{< term "health-check" "health check" >}} to `/healthz` on every backend every 20 ms and marks a backend down after 2 failed probes. In the experiment I waited until the dead backend was removed before sending the 30 requests, so none failed, and the traffic went to `b0` and `b2` half and half. In real life requests that arrive before the removal can still fail.

Active checks cost extra traffic and can be late, and passive checks need real failures. Production systems usually combine both, and add a retry for requests that are safe to repeat ({{< term "idempotency" "idempotent" >}} ones). I did not add retries to this demo.

## Algorithms: round robin and least connections

Round robin gives every backend the same number of requests and ignores how busy it is. To see why that can hurt, I made `b0` slow (100 ms for every request) and sent 60 requests with 6 workers at the same time. I compared round robin (`rr`) with least connections (`lc`), which sends each request to the backend that currently has the fewest requests in progress:

```
rr: b0(slow)=20 b1=20 b2=20
lc: b0(slow)=2 b1=35 b2=23
```

Round robin gave the slow backend a full third of the work. Least connections noticed that `b0` always had unfinished requests, so it received only 2. The split between `b1` and `b2` is not fixed: I saw `b1=33 b2=25` and `b1=35 b2=23` in two runs. There is another well-known idea, "power of two random choices" (pick two backends at random and take the less loaded one), which I mention but did not run.

## Layer 4 or layer 7?

If layer 7 can do all of this, why would anyone use layer 4? Because it also costs something.

- Layer 7 can route by path or header, edit headers, retry, spread HTTP/2 requests and terminate {{< term "tls" "TLS" >}}. For that it must buffer and parse every request, it holds the private key when it terminates TLS, and it is one more component that has to understand your protocol (with gRPC it needs HTTP/2 and trailers support).
- Layer 4 is simpler and works for any protocol on TCP. It cannot see inside, which has one benefit: with TLS passthrough it forwards encrypted bytes without holding any key, but then it cannot see paths either. With termination, a layer 7 balancer decrypts the traffic, and often encrypts it again toward the backend.

I only describe the TLS part here; certificates are covered in [TLS and certificates with openssl](/posts/net-tls-openssl/).

## Load balancing traps

- **Long-lived connections with layer 4.** HTTP/2, gRPC and WebSocket clients keep one connection for a long time, so a layer 4 balancer pins each client to one backend. Use layer 7 balancing for them, or let the client balance itself.
- **Trusting `X-Forwarded-For` from anyone.** The header is just text that any client can send. Believe it only when the request came from your own proxy, and let your proxy set it itself instead of passing along what the client sent.
- **Relying on one kind of failure detection.** Passive detection sacrifices a real request, and active detection can be late. Combine them, and limit retries to idempotent requests.
- **`hash % N` for sticky routing.** When N changes, almost every key moves. Use a ring or another consistent scheme when the pool changes often.

## Exercise

Add an `lc` mode test with a backend that is slow only for `/report`. Does the number of connections in progress still show the real load? What would you track instead?

## What's next

The next post is "Network troubleshooting with curl, dig and traceroute". A balancer is one more box between the client and the server, and when a request fails you need a method for finding which box, and which layer, broke.
