+++
date = '2027-01-29T10:00:00+03:30'
draft = false
title = 'KV and Object Store in NATS'
description = 'Use JetStream as a key-value store and a blob store from Go: revisions, compare-and-swap, watch, TTL, a simple lock, and chunked objects, with real output.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "kv", "object-store", "messaging"]
cover = { image = "/images/covers/nats-kv-object-store.png", alt = "KV and Object Store in NATS", hiddenInSingle = true }
+++

In the [previous post](/posts/nats-jetstream-testing/) we tested JetStream services with an embedded server. This post uses the same trick for something new: JetStream also works as a **key-value store** (KV) and a **blob store** (Object Store). Both are built on streams, so there is nothing extra to run. They are handy for small shared state: feature flags, short-lived locks, [dedup keys](/posts/nats-jetstream-idempotency/), or a file that several services need.

> Go 1.26, `nats-server` v2.15.1, `nats.go` v1.54.0, using the newer `jetstream` package (it has KV and Object Store). One embedded server in the demo program. The machine was busy, so I only quote rough times.

## Create a bucket, put and get

```go
kv, _ := js.CreateKeyValue(ctx, jetstream.KeyValueConfig{
	Bucket: "Config", History: 5, Storage: jetstream.FileStorage,
})
r1, _ := kv.Put(ctx, "feature.checkout", []byte("off"))
r2, _ := kv.Put(ctx, "feature.checkout", []byte("on"))
e, _ := kv.Get(ctx, "feature.checkout")
hist, _ := kv.History(ctx, "feature.checkout")
```

```
put revisions: 1 2
get: key=feature.checkout value=on revision=2 op=KeyValuePutOp
get missing: nats: key not found true
history: rev=1 value=off
history: rev=2 value=on
```

`History` is how many old values per key are kept (default 1, maximum 64). A **revision** is the stream sequence number of the write, so it is unique across the whole bucket, not per key. Other useful config fields are `TTL` (expiry) and `Storage` (file or memory).

## It is just a stream

```
stream=KV_Config subjects=[$KV.Config.>] max_msgs_per_subject=5 storage=File msgs=2
raw message: subject=$KV.Config.feature.checkout seq=2 data=on
```

The bucket `Config` is a stream named `KV_Config`. Each key is a subject, `$KV.Config.<key>`, and `History` becomes `max_msgs_per_subject`. `Get` reads the last message of that subject. So everything you know about streams (replicas, storage, `nats stream info`) applies.

## Create and Update: compare-and-swap

`Create` succeeds only if the key does not exist. `Update` succeeds only if you pass the key's current revision.

```
create: 3 <nil>
create again: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 3: key exists | is ErrKeyExists: true
update with current rev: 4 <nil>
update stale: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 4: nats: key revision mismatch
is ErrKeyRevisionMismatch: true
```

Both are the server's `wrong last sequence` check (error code 10071) underneath. In Go, use `errors.Is` with `jetstream.ErrKeyExists` and `jetstream.ErrKeyRevisionMismatch`. The usual loop is: `Get`, compute, `Update` with that revision, and on a mismatch `Get` again and retry. No locks needed.

## Delete vs Purge, and history

I wrote keys `a` and `b` twice each, then `Delete(a)` and `Purge(b)`:

```
get a after delete: nats: key not found
history a (3 entries): [rev=5 op=KeyValuePutOp] [rev=6 op=KeyValuePutOp] [rev=9 op=KeyValueDeleteOp]
history b (1 entries): [rev=10 op=KeyValuePurgeOp]
keys: [feature.checkout limit]
```

`Delete` appends a delete marker and keeps the old values in history. `Purge` also writes a marker but removes the older values. Both make `Get` return `ErrKeyNotFound`.

## Watch

```go
w, _ := kv.WatchAll(ctx)
for e := range w.Updates() {
	if e == nil { fmt.Println("nil (initial values done)"); continue }
	fmt.Println(e.Key(), string(e.Value()), e.Revision(), e.Operation())
}
```

With two keys already present, then two puts and a delete from another goroutine:

```
watch: dark=off rev=1 op=KeyValuePutOp
watch: beta=off rev=2 op=KeyValuePutOp
watch: nil (initial values done)
watch: dark=on rev=3 op=KeyValuePutOp
watch: gamma=on rev=4 op=KeyValuePutOp
watch: beta= rev=5 op=KeyValueDeleteOp
```

First the current value of every key, then a `nil` entry meaning "you have caught up", then live changes, deletes included. A service can use this to keep a local cache of its config. `Watch` takes a key pattern, and options like `UpdatesOnly()` and `IgnoreDeletes()` exist.

## TTL and a tiny lock

A bucket with `TTL: time.Second` drops entries after a second. I poll with a deadline instead of sleeping:

```
get right after put: <nil>
gone after ~1.3s: nats: key not found
```

(Expiry is not instant: with a 1 s TTL I saw about 1.3 s on a busy machine, so never rely on exact timing.) Combine `Create` and TTL and you get a lock that frees itself if its owner dies. In the demo `worker-a` takes `nightly-report` and "crashes", then `worker-b` and `worker-c` retry `Create` in a loop; the winner releases with `Delete`:

```
+0.0s worker-a: create lock: err=<nil>
+1.3s worker-c: got the lock
+1.4s worker-b: got the lock
+1.5s done
```

Only one at a time held it. Note this is a simple lease, not a safe mutex: if the owner is just slow and the TTL passes, someone else gets the lock too. Keep the work idempotent. The same `Create` also makes a fine dedup check, and for stopping workers cleanly see [graceful shutdown](/posts/go-graceful-shutdown-workers/).

## Object Store

KV values are small. For big things there is the Object Store. I generated 5 MB + 123 bytes of random data and checked the round trip with SHA-256:

```
generated 5243003 bytes sha256=814fa28020cf3b71
put: name=report.bin size=5243003 chunks=41 digest=SHA-256=gU-igCDPO3F_4IIRwRPdwils9n-F89Us246F7Q2bgTo= nuid=...
get: 5243003 bytes sha256=814fa28020cf3b71 equal=true
list: report.bin size=5243003 chunks=41
list: small.txt size=5 chunks=1
stream=OBJ_Files subjects=[$O.Files.C.> $O.Files.M.>] msgs=44 bytes=5246313
```

The default chunk is 128 KB, so the blob became 41 messages (40 full chunks and 123 bytes). `.C.` subjects hold chunks and `.M.` subjects hold metadata, so 44 messages = 41 + 1 chunk of `small.txt` + 2 metadata. After `Delete("report.bin")`:

```
info after delete: nats: object not found
after delete: msgs=3 bytes=671
status: bucket=Files size=671 sealed=false storage=File replicas=1
```

Delete removes the chunks and leaves a metadata marker.

## A few things to watch

- This is not a database: no queries, no transactions across keys, only per-key revisions. Treat it as small shared state.
- TTL is a bucket setting here, so use one bucket per lifetime (locks, sessions, config).
- Values go through normal NATS messages, so the server's max payload (1 MB by default) limits a KV value; use Object Store beyond that.
- The Object Store checks a digest on `Get`, but it is still chunks in a stream: mind storage limits and replicas.
- Watchers must handle the `nil` entry and delete markers.

## What's next

Next: JetStream in production, covering clustering, retention and security.
