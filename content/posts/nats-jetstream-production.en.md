+++
date = '2027-02-16T10:00:00+03:30'
draft = false
title = 'JetStream in production: clustering, retention and security'
seoTitle = 'JetStream in Production: Clustering and Security'
description = 'Run JetStream with three replicas, survive a node loss, pick a retention policy and lock it down with permissions and TLS, all shown with real runs in Go.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "cluster", "security", "production", "retention"]
cover = { image = "/images/covers/nats-jetstream-production.png", alt = "JetStream in production: clustering, retention and security", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/nats-kv-object-store/) we used JetStream as a KV and blob store. This last post of the series is about what changes when it leaves your laptop: one server becomes three, streams need a retention plan, and not everyone should be allowed to publish everywhere. Monitoring and tests come first, so see [observability](/posts/nats-jetstream-observability/) and [testing](/posts/nats-jetstream-testing/); for shutting your workers down cleanly see [graceful shutdown](/posts/go-graceful-shutdown-workers/).

> Go 1.26, `nats-server` v2.15.1 and `nats.go` v1.54.0. All servers are embedded in the demo programs and run on localhost. The machine was not idle, so I give no timings.

## Clustering and replicas

Three servers form a cluster by listing each other as `Routes`. Each one needs its own name and its own `StoreDir`:

```go
opts := &server.Options{
	ServerName: "n1", Host: "127.0.0.1", Port: clientPort,
	JetStream: true, StoreDir: root + "/n1",
	Cluster: server.ClusterOpts{Name: "demo", Host: "127.0.0.1", Port: clusterPort},
	Routes:  server.RoutesFromStr(allThreeClusterURLs),
}
```

A stream is replicated with `Replicas: 3`. Each stream is a small **Raft** group: one leader takes the writes, the others copy them, and a write counts only when a **majority** has it. With three nodes the majority is two, so you can lose one node and keep going. Lose two and the stream stops, because it can no longer reach a majority. That is on purpose: it prefers to refuse writes over splitting into two histories.

I published 100 messages, then stopped the leader while the client was connected to it, published 100 more, and then stopped a second node:

```
before: msgs=100 leader=n1 replicas=[n2 current=true offline=false] [n3 current=true offline=false]
stopping leader n1
  [client] disconnected: read tcp 127.0.0.1:51843->127.0.0.1:51806: read: connection reset by peer
  [client] reconnected to n2
  publish error: context deadline exceeded
published after failover: ok=100 retried-errors=1
after 1 down: msgs=200 leader=n3 replicas=[n1 current=false offline=true] [n2 current=true offline=false]
stopping second node n2
publish with 1 of 3 up: context deadline exceeded | timeout: true | no responders: false
```

The client reconnected by itself, a new leader (n3) was elected, and the count went from 100 to exactly 200. One publish timed out during the election (my timeout was 3 seconds) and I retried it, so your publisher needs a retry too. With one node left, the publish timed out instead of succeeding.

The client settings that matter:

```go
nc, _ := nats.Connect(urls, nats.MaxReconnects(-1), nats.ReconnectWait(200*time.Millisecond),
	nats.ReconnectBufSize(1<<20), nats.DisconnectErrHandler(logIt))
```

`-1` means never give up, `ReconnectBufSize` is how many bytes are buffered while disconnected, and the handler is where you log or count outages.

## Retention: what stays in the stream

Three policies, one experiment each: publish 3 messages, consume and ack all of them, then count what is left.

```
LIM       after ack of all 3: msgs=3
INT       before any consumer: msgs=0
INT       after ack of all 3: msgs=0
WQ        after ack of all 3: msgs=0
WQ second overlapping consumer: nats: API error: code=400 err_code=10100 description=filtered consumer not unique on workqueue stream
```

`LimitsPolicy` (default) keeps messages until a limit removes them, whatever the consumers do. `InterestPolicy` keeps a message only while some consumer still has to ack it; with no consumer at all, nothing is stored. `WorkQueuePolicy` removes a message on its first ack, and consumers must not overlap.

Limits protect the disk. With `MaxMsgs: 3` and five publishes:

```
MAXOLD: msgs=3 first_seq=3 last_seq=5
MAXNEW publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW: msgs=3 first_seq=1 last_seq=3
```

`DiscardOld` drops the oldest, so publishing never fails. `DiscardNew` keeps the old ones and rejects new publishes, which pushes the problem back to the producer. `MaxBytes` behaves the same (I got `maximum bytes exceeded`). `MaxAge: time.Second` took 3 messages to 0 after 2 seconds. Storage is `FileStorage` (survives restarts) or `MemoryStorage`; use memory only for data you can lose. The cluster demo used file storage.

## Security

Without a config, anybody who can reach the port can do anything. Users with subject permissions are the first step:

```go
{Username: "orders", Password: "orders-pw", Permissions: &server.Permissions{
	Publish:   &server.SubjectPermission{Allow: []string{"orders.>", "$JS.API.>"}},
	Subscribe: &server.SubjectPermission{Allow: []string{"_INBOX.>", "orders.>"}},
}}
```

JetStream clients talk to the server over `$JS.API.*` subjects, and replies come back on `_INBOX.>`, so a client needs those permissions too. A reader may get only the consumer subjects.

```
wrong password:       nats: Authorization Violation
publish orders.new:   1 <nil>
publish billing.*:    context deadline exceeded
async error handler:  nats: permissions violation: Permissions Violation for Publish to "billing.invoice"
subscribe billing.>:  nats: permissions violation: Permissions Violation for Subscription to "billing.>"
reader create stream: context deadline exceeded
reader create consumer: <nil>
```

Note how a forbidden publish shows up: the call only times out, and the real reason arrives in the connection's `ErrorHandler`. Always set one.

For TLS I generated a throwaway CA and a server certificate in Go with `crypto/x509`, and gave the server `TLSConfig`:

```
TLS, system roots:    nats: tls error: tls: failed to verify certificate: x509: “nats” certificate is not trusted
TLS, wrong CA:        nats: tls error: tls: failed to verify certificate: x509: certificate signed by unknown authority
TLS, wrong hostname:  nats: tls error: tls: failed to verify certificate: x509: certificate is valid for localhost, not wrong.example
TLS, right CA:        <nil>   (TLS 1.3)
```

Verification stays on; `InsecureSkipVerify` also connects, but it removes the whole point. NATS also supports nkeys, JWT and accounts for multi-tenant setups. I did not try them here.

## A few things to watch

- Replicas are not backups. A bad publish or a purge is replicated too.
- Use an odd number of nodes, and `Replicas` of 3 for anything you care about.
- Not tested: nodes on different hosts or networks, a real disk failure, and a partition between nodes. All servers here shared one machine.
- Size your limits before launch, and decide `DiscardOld` or `DiscardNew` on purpose.
- Give each service the minimum permissions, and always keep TLS verification on.

## What's next

This is the last post of the NATS JetStream series. The calendar goes back to the Rust series next, with unsafe and FFI in Rust.
