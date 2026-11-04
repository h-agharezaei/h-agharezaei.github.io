+++
date = '2027-02-16T10:00:00+03:30'
draft = false
title = 'JetStream in production: clustering, retention and security'
seoTitle = 'JetStream in Production: Clustering and Security'
description = 'Run JetStream with three replicas, survive a node loss, pick a retention policy and lock it down with permissions and TLS, all shown with real runs in Go.'
contentType = 'engineering'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "cluster", "security", "production", "retention"]
cover = { image = "/images/covers/nats-jetstream-production.png", alt = "JetStream in production: clustering, retention and security", hiddenInSingle = true }
+++

Picture the day your single NATS server needs a kernel update. While it reboots, nothing can be published and every worker waits. Or the day a new contractor's laptop joins the office network and can reach the NATS port. Without a config file, anybody who can reach that port can publish to any subject, read any stream and delete it. That is fine on a laptop. It is not fine once JetStream leaves it.

This last post of the series is about what changes on the way to production. One server becomes three, so the cluster survives a node loss. Streams need a retention plan, so they do not fill the disk. And not everyone should be allowed to publish everywhere, so we add users, permissions and TLS. The [previous post](/posts/nats-kv-object-store/) used JetStream as a KV and blob store. Monitoring and tests come before going live, so see [observability](/posts/nats-jetstream-observability/) and [testing](/posts/nats-jetstream-testing/). For shutting your workers down cleanly, see [graceful shutdown](/posts/go-graceful-shutdown-workers/).

> I re-ran all three demos with Go 1.27, `nats-server` v2.15.1 and `nats.go` v1.54.0. All servers are embedded in the demo programs and listen on `127.0.0.1` only. (One demo originally started its server without a host, so it listened on all interfaces. For this re-run I ran a scratch copy bound to 127.0.0.1 and did not change the original demo.) The machine was not idle, so I give no timings. The three demo servers share one machine, which matters for what they can prove: see the checklist at the end.

## Clustering and replicas

The idea first. A **cluster** is several NATS servers that know about each other and act as one. A stream can keep a copy of its data on each of them. The setting is `Replicas`: with `Replicas: 3`, the stream is stored on three servers.

How do three copies stay the same? JetStream uses **{{< term "raft" "Raft" >}}** for this. Each replicated stream is a small Raft group. One server is the leader and takes the writes. The others copy what the leader writes. A write counts as done only when a **majority** (a {{< term "quorum" "quorum" >}}) has it. With three servers the majority is two, so you can lose one server and keep going. Lose two, and the stream stops, because it can no longer reach a majority. That is on purpose: the stream prefers to refuse writes over splitting into two different histories.

To build a cluster, the servers list each other as `Routes`. Each one needs its own name and its own `StoreDir`:

```go
opts := &server.Options{
	ServerName: "n1", Host: "127.0.0.1", Port: clientPort,
	JetStream: true, StoreDir: root + "/n1",
	Cluster: server.ClusterOpts{Name: "demo", Host: "127.0.0.1", Port: clusterPort},
	Routes:  server.RoutesFromStr(allThreeClusterURLs),
}
```

The stream itself is created with three replicas:

```go
js.CreateStream(ctx, jetstream.StreamConfig{Name: "ORDERS", Subjects: []string{"orders.>"},
	Replicas: 3, Storage: jetstream.FileStorage})
```

The demo does this, in order: start three servers in one process, publish 100 messages, then stop the leader while the client is connected to it, publish 100 more, and finally stop a second server and try to publish again. A helper prints the stream's state after each step. This is the real output of one run:

```text
before: msgs=100 leader=n1 replicas=[n2 current=true offline=false] [n3 current=true offline=false] 
client now connected to: n1
stopping leader n1
  [client] disconnected: EOF
  [client] reconnected to n2
published after failover: ok=100 retried-errors=0
after 1 down: msgs=200 leader=n2 replicas=[n1 current=false offline=true] [n3 current=true offline=false] 
stopping second node n3
publish with 1 of 3 up: context deadline exceeded | timeout: true | no responders: false
  [client] disconnected: EOF
```

Line by line:

- `before`: 100 messages stored. The leader is `n1`, and both followers (`n2`, `n3`) are `current=true`, meaning they have caught up with the leader.
- `client now connected to: n1`: I made the client connect to the leader first, so that stopping the leader forces a reconnect.
- `stopping leader n1`, then the client prints that it was disconnected and `reconnected to n2` by itself. It had all three addresses in its list.
- `published after failover: ok=100 retried-errors=0`: all 100 new messages went through. A new leader was elected in the background.
- `after 1 down`: the count is exactly 200, so nothing was lost or duplicated. The leader is now `n2`, and `n1` shows `offline=true`.
- `stopping second node n3` and `publish with 1 of 3 up: context deadline exceeded`: with one server left there is no majority, so the publish does not succeed and times out. It is not "no responders": the stream exists and the server is there, it just cannot commit.
- The last `[client] disconnected` line is the demo shutting down.

The details of the failover change from run to run. In this run the leader was `n1`, and in other runs it was `n3`. In an earlier run (the original one for this post) one publish timed out during the election, because the new leader was not elected yet, and my retry loop sent it again (the client timeout was 3 seconds). On some runs the demo also prints a few `retry:` lines at startup while the three servers are still finding each other. So your publisher needs a retry, and a publish error right after a node loss is normal, not a bug.

The client settings that matter:

```go
nc, _ := nats.Connect(urls, nats.MaxReconnects(-1), nats.ReconnectWait(200*time.Millisecond),
	nats.ReconnectBufSize(1<<20), nats.DisconnectErrHandler(logIt))
```

`-1` means never give up reconnecting. `ReconnectWait` is the pause between attempts. `ReconnectBufSize` is how many bytes the client buffers while it is disconnected. The handler is where you log or count outages.

## Retention: what stays in the stream

The second production question is how long messages stay. By default a stream just keeps growing. **Retention** is the rule for when a message may be removed. JetStream has three policies, and the quickest way to understand them is an experiment: publish 3 messages, consume and ack all of them with one consumer, and count what is left in the stream.

```text
LIM       published 3:        msgs=3
LIM       after ack of all 3: msgs=3
INT       before any consumer: msgs=0
INT       published 3:        msgs=3
INT       after ack of all 3: msgs=0
WQ        published 3:        msgs=3
WQ        after ack of all 3: msgs=0
WQ second overlapping consumer: nats: API error: code=400 err_code=10100 description=filtered consumer not unique on workqueue stream
```

The three streams are named after their policy. Reading it:

- `LimitsPolicy` (`LIM`, the default) keeps messages until a limit removes them, whatever the consumers do. After the ack, all 3 are still there.
- `InterestPolicy` (`INT`) keeps a message only while some consumer still has to ack it. Before any consumer exists, nobody is interested, so a message published then is not stored at all (`msgs=0`). Once a consumer exists, messages are kept until it acks them, and after the ack they are gone.
- `WorkQueuePolicy` (`WQ`) removes a message on its first ack, which is exactly a work queue. The last line shows the restriction: a second consumer whose filter overlaps the first one is rejected, so each message can only belong to one consumer.

Retention decides when a message is no longer needed. **Limits** protect the disk by deciding what happens when a stream gets too big. With `MaxMsgs: 3` and five publishes, once with each discard policy:

```text
MAXOLD: msgs=3 first_seq=3 last_seq=5
MAXNEW publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW publish #5: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW: msgs=3 first_seq=1 last_seq=3
```

`DiscardOld` (`MAXOLD`) drops the oldest message to make room, so publishing never fails: it kept sequences 3 to 5. `DiscardNew` (`MAXNEW`) keeps the old ones and rejects new publishes, which pushes the problem back to the producer: publishes #4 and #5 failed and the stream still holds sequences 1 to 3. Which one is right depends on which loss you can live with: losing the oldest data, or refusing the newest.

`MaxBytes` behaves the same way. I used a 1 KiB limit, `DiscardNew` and 400-byte messages:

```text
publish #3: nats: nats: API error: code=503 err_code=10077 description=maximum bytes exceeded
publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum bytes exceeded
BYTES: msgs=2 bytes=842
```

Two messages fit. A stored message counts slightly more than its payload (842 bytes for two 400-byte payloads), and a third would pass 1024, so it was rejected. `MaxAge: time.Second` expires messages by age:

```text
AGE right away: msgs = 3
AGE after 2s:   msgs = 0
```

Storage is `FileStorage` (survives restarts) or `MemoryStorage` (fast, but gone if the server stops). Use memory only for data you can lose. The cluster demo used file storage. The retention demo used memory, because it is only counting messages.

## Security

Back to the opening. Without a config, anybody who can reach the port can do anything. The first step is users with subject permissions: each user may publish only to some subjects and subscribe only to some. Here is one user, `orders`, who may use `orders.>` (every subject under `orders.`):

```go
{Username: "orders", Password: "orders-pw", Permissions: &server.Permissions{
	Publish:   &server.SubjectPermission{Allow: []string{"orders.>", "$JS.API.>"}},
	Subscribe: &server.SubjectPermission{Allow: []string{"_INBOX.>", "orders.>"}},
}}
```

The extra entries are needed because JetStream clients talk to the server over `$JS.API.*` subjects, and replies come back on `_INBOX.>`. A client without those permissions cannot even create a consumer. A read-only user can get just the consumer subjects. (The passwords here are throwaway values for the demo.)

The demo connects as different users and tries things it should not be allowed to do:

```text
no credentials:       nats: Authorization Violation
wrong password:       nats: Authorization Violation
publish orders.new:   1 <nil>
publish billing.*:    context deadline exceeded
async error handler:  nats: permissions violation: Permissions Violation for Publish to "billing.invoice"
subscribe billing.>:  nats: permissions violation: Permissions Violation for Subscription to "billing.>"
reader create stream: context deadline exceeded
reader stream info:   <nil>
reader create consumer: <nil>
reader got: orders.new ack: <nil>
```

- Connecting with no credentials, or a wrong password, is refused.
- `orders` can publish `orders.new` (the ack says sequence 1).
- `orders` publishing to `billing.invoice` is forbidden. Note how it shows up: the call only times out, and the real reason (`Permissions Violation for Publish`) arrives later in the connection's `ErrorHandler`. Always set one, or you will just see timeouts.
- The same for subscribing to `billing.>`.
- The `reader` user cannot create a stream (it only times out; the demo reads and discards the matching message from the error handler), but it can read the stream info, create a consumer, fetch a message and ack it.

Permissions say who may do what. TLS protects the connection, so nobody on the network can read or change the traffic, and so the client knows it is talking to the real server. For the demo I generated a throwaway certificate authority (CA) and a server certificate in Go with `crypto/x509`, and gave the server a `TLSConfig`. Then four clients try to connect with different trust settings:

```text
TLS, system roots:    nats: tls error: tls: failed to verify certificate: x509: “nats” certificate is not trusted
TLS, wrong CA:        nats: tls error: tls: failed to verify certificate: x509: certificate signed by unknown authority
TLS, wrong hostname:  nats: tls error: tls: failed to verify certificate: x509: certificate is valid for localhost, not wrong.example
TLS, right CA:        <nil>
negotiated:           TLS 1.3
skip verify (never in prod): <nil>
```

The first three clients refuse the server, each for a different reason: the certificate comes from a CA the system does not know, from a different CA, or is for a different hostname. (The exact wording of the first message comes from the operating system's verifier, so it differs on other systems.) Only the client that trusts the right CA connects, and it negotiated TLS 1.3. The last line shows that `InsecureSkipVerify` also connects, but it removes the whole point of TLS, so keep verification on.

NATS also supports nkeys, {{< term "jwt" "JWT" >}}-based credentials and accounts for multi-tenant setups. I did not try them here.

## Pre-launch checklist

- Replicas are not backups. A bad publish or a purge is replicated too.
- Use an odd number of nodes, and `Replicas` of 3 for anything you care about.
- Not tested: nodes on different hosts or networks, a real disk failure, and a partition between nodes. All servers here shared one machine, so the demo shows leader election and failover, not how the cluster behaves when the network between nodes breaks.
- Size your limits before launch, and decide `DiscardOld` or `DiscardNew` on purpose.
- Give each service the minimum permissions, and always keep TLS verification on.
- Set an `ErrorHandler` on every connection, because permission errors do not arrive as errors from the publish call.

## What's next

This is the last post of the NATS JetStream series. The Rust series continues with [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/), which steps outside safe Rust to call C and expose a C-ABI library.
