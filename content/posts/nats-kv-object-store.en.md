+++
date = '2027-01-29T10:00:00+03:30'
draft = false
title = 'KV and Object Store in NATS'
description = 'Use JetStream as a key-value store and a blob store from Go: revisions, compare-and-swap, watch, TTL, a simple lock, and chunked objects, with real output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "kv", "object-store", "messaging"]
cover = { image = "/images/covers/nats-kv-object-store.png", alt = "KV and Object Store in NATS", hiddenInSingle = true }
+++

Say you have a few services that all need to read the same small piece of configuration, such as a feature flag that turns the new checkout on. You want three things. A service should be able to read the flag. It should be told right away when somebody changes it, without polling. And two people changing the flag at the same time should not silently overwrite each other. A different day, one of the services needs to share a 5 MB report file with another. You could run a separate database or file store for each of these, or you could notice that you already run something that can do both.

If your services already use JetStream, it can: JetStream also works as a **key-value store** (KV) and a **blob store** (Object Store). Both are built on top of streams, so there is nothing extra to run. The embedded server from the [previous post](/posts/nats-jetstream-testing/) is enough to try them. Typical uses are feature flags, short-lived locks, [dedup keys](/posts/nats-jetstream-idempotency/), or a file that several services need.

> I ran everything with Go 1.27, `nats-server` v2.15.1 and `nats.go` v1.54.0, using the newer `jetstream` package (it has KV and Object Store). The demo is one local program with one embedded server. The code is a local example, not a published repo. The machine was busy, so I only quote rough times, and the random IDs in the output (like `nuid`) differ on every run.

## Create a bucket, put and get

A KV store is a **bucket** of keys and values. You put a value under a key and get it back. The twist is that every write gets a **revision**, a number that tells you which write it was. That small number is what makes watching and safe updates possible later in this post.

In the first demo I create a bucket called `Config`, write the same key twice and read it back:

```go
kv, _ := js.CreateKeyValue(ctx, jetstream.KeyValueConfig{
	Bucket: "Config", History: 5, Storage: jetstream.FileStorage,
})
r1, _ := kv.Put(ctx, "feature.checkout", []byte("off"))
r2, _ := kv.Put(ctx, "feature.checkout", []byte("on"))
e, _ := kv.Get(ctx, "feature.checkout")
hist, _ := kv.History(ctx, "feature.checkout")
```

```text
put revisions: 1 2
get: key=feature.checkout value=on revision=2 op=KeyValuePutOp
get missing: nats: key not found true
history: rev=1 value=off
history: rev=2 value=on
```

Line by line:

- `put revisions: 1 2`: the two writes got revisions 1 and 2.
- `get`: reading the key returns the latest value, `on`, with revision 2. `op=KeyValuePutOp` says this entry was created by a put (the other kinds are delete and purge, below).
- `get missing`: reading a key that does not exist returns an error. In Go you test it with `errors.Is(err, jetstream.ErrKeyNotFound)`, and the trailing `true` is that check.
- `history`: both values are still there, oldest first, because the bucket keeps history.

`History` is how many old values per key the bucket keeps (the default is 1 and the maximum is 64). A revision is the stream sequence number of the write, so it is unique across the whole bucket, not per key. Other useful config fields are `TTL` (expiry, used later) and `Storage` (file or memory).

## It is just a stream

If KV is "built on streams", we can look under the hood and see it. The demo reads the stream info and the raw message:

```text
stream=KV_Config subjects=[$KV.Config.>] max_msgs_per_subject=5 storage=File msgs=2
raw message: subject=$KV.Config.feature.checkout seq=2 data=on
```

The bucket `Config` is a stream named `KV_Config`. Each key is a subject, `$KV.Config.<key>`, and `History: 5` became `max_msgs_per_subject=5`, which means "keep at most 5 messages per subject". `msgs=2` is our two writes. `Get` simply reads the last message of that subject, and that message's stream sequence (`seq=2`) is the revision. So everything you know about streams (replicas, storage, `nats stream info`) applies to a bucket as well.

## Create and Update: compare-and-swap

Now the problem of two people changing the same flag. Suppose two services both read a counter whose value is 5, and both write 6. One increment is lost, and nobody gets an error. A common fix is **compare-and-swap**: "write this new value only if the key is still at the revision I read". If somebody else changed it in between, the write is refused, and you read again. This is the same idea as {{< term "optimistic-concurrency" "optimistic concurrency" >}}: no lock, just a check at write time.

KV offers two calls for this. `Create` succeeds only if the key does not exist. `Update` succeeds only if you pass the key's current revision. The demo tries each, including the failing cases:

```text
create: 3 <nil>
create again: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 3: key exists | is ErrKeyExists: true
update with current rev: 4 <nil>
update stale: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 4: nats: key revision mismatch
api error code: 10071 | wrong last sequence: 4
is ErrKeyRevisionMismatch: true
```

- The first `create` made the key `limit` at revision 3 (revisions 1 and 2 were the earlier writes).
- The second `create` of the same key failed. `wrong last sequence: 3` says the key's last revision is 3, so a "create" is not allowed.
- `update with current rev` passed revision 3 and succeeded; the new revision is 4.
- `update stale` passed revision 1, which is old. The server answered `wrong last sequence: 4`, that is, "the key is at 4, not 1", and the library reports it as a revision mismatch.

Both failures are the server's `wrong last sequence` check (error code 10071) underneath. In Go, use `errors.Is` with `jetstream.ErrKeyExists` and `jetstream.ErrKeyRevisionMismatch`. The usual loop is: `Get`, compute the new value, `Update` with the revision you read, and on a mismatch `Get` again and retry. No locks are needed.

## Delete vs Purge, and history

There are two ways to remove a key, and they differ in what happens to the history. In the demo I wrote keys `a` and `b` twice each, then called `Delete(a)` and `Purge(b)`:

```text
get a after delete: nats: key not found
history a (3 entries): [rev=5 op=KeyValuePutOp] [rev=6 op=KeyValuePutOp] [rev=9 op=KeyValueDeleteOp]
history b (1 entries): [rev=10 op=KeyValuePurgeOp]
keys: [feature.checkout limit]
```

`Delete` appends a delete marker and keeps the old values in the history: `a` has its two puts (revisions 5 and 6) and the marker (revision 9). Revisions 7 and 8 belong to `b`, which shows again that revisions count across the whole bucket. `Purge` also writes a marker (revision 10) but removes the older values, so `b` has one entry. Both make `Get` return `ErrKeyNotFound`, and `Keys` no longer lists them: only `feature.checkout` and `limit` are left.

## Watch

Now the second thing from the opening: being told when a value changes. A **watch** is a subscription to a bucket. The code reads from the watcher's `Updates()` channel:

```go
w, _ := kv.WatchAll(ctx)
for e := range w.Updates() {
	if e == nil { fmt.Println("nil (initial values done)"); continue }
	fmt.Println(e.Key(), string(e.Value()), e.Revision(), e.Operation())
}
```

In the demo the bucket already holds two keys. After the watch starts, another goroutine does two puts and a delete:

```text
watch: dark=off rev=1 op=KeyValuePutOp
watch: beta=off rev=2 op=KeyValuePutOp
watch: nil (initial values done)
watch: dark=on rev=3 op=KeyValuePutOp
watch: gamma=on rev=4 op=KeyValuePutOp
watch: beta= rev=5 op=KeyValueDeleteOp
```

The first two lines are the current value of every key. Then comes a `nil` entry, which means "you have caught up with the present". After that come the live changes: `dark` turned on, a new key `gamma`, and `beta` deleted (its value is empty). A service can use this to keep a local cache of its config: fill the cache from the first part, then apply changes as they arrive, with no polling. `Watch` takes a key pattern, and options like `UpdatesOnly()` and `IgnoreDeletes()` exist.

## TTL and a tiny lock

A bucket can also make entries expire. A bucket with `TTL: time.Second` drops entries a second after they are written. The demo writes a session key and polls with a deadline instead of sleeping:

```text
get right after put: <nil>
gone after ~1.3s: nats: key not found
```

The first line means the read worked (`<nil>` is "no error"). The second means the key vanished by itself after about 1.3 seconds. Expiry is not instant: with a 1 s TTL I saw about 1.3 s on a busy machine, so never rely on exact timing.

Combine `Create` and a TTL and you get a lock that frees itself if its owner dies. `Create` is the lock acquisition, because only one caller can create the key. The TTL is the safety net. In the demo, `worker-a` takes the lock `nightly-report` and "crashes" by never releasing it. Then `worker-b` and `worker-c` retry `Create` in a loop. Whoever wins holds the lock for 100 ms and releases it with `Delete`:

```text
+0.0s worker-a: create lock: err=<nil>
+1.3s worker-c: got the lock
+1.5s worker-b: got the lock
+1.6s done
```

Nobody could take the lock for the first 1.3 seconds, until worker-a's entry expired. Then `worker-c` won and `worker-b` got it only after `worker-c` released it, so only one held it at a time. The winner can differ on each run, and an earlier run printed `+1.4s` for `worker-b` and `+1.5s` for `done`.

Note that this is a simple lease, not a safe mutex. If the owner is just slow and the TTL passes, someone else gets the lock too. Keep the work idempotent. The same `Create` also makes a fine dedup check, and for stopping workers cleanly see [graceful shutdown](/posts/go-graceful-shutdown-workers/).

## Object Store

KV values are small, since each one is a NATS message. For big things there is the Object Store. It splits a large blob into chunks, stores each chunk as a message, and puts them back together on `Get`. The demo generates 5 MB + 123 bytes of pseudo-random data and checks the round trip with SHA-256:

```text
generated 5243003 bytes sha256=814fa28020cf3b71
put: name=report.bin size=5243003 chunks=41 digest=SHA-256=gU-igCDPO3F_4IIRwRPdwils9n-F89Us246F7Q2bgTo= nuid=OBH4NbUJ2ckiDHP87U2H7F
get: 5243003 bytes sha256=814fa28020cf3b71 equal=true
list: report.bin size=5243003 chunks=41
list: small.txt size=5 chunks=1
stream=OBJ_Files subjects=[$O.Files.C.> $O.Files.M.>] msgs=44 bytes=5246313
```

- The first line prints the first 8 bytes of the SHA-256 of what we generated. `get` prints the same value for what came back, and `equal=true` confirms they match.
- `put` shows the object stored as 41 chunks, with a SHA-256 digest of the content.
- The default chunk is 128 KB, so the blob became 41 messages: 40 full chunks and a last one of 123 bytes.
- `.C.` subjects hold chunks and `.M.` subjects hold metadata, so 44 messages = 41 chunks + 1 chunk of `small.txt` + 2 metadata messages (one per object).

Then the demo deletes the large object:

```text
info after delete: nats: object not found
after delete: msgs=3 bytes=671
status: bucket=Files size=671 sealed=false storage=File replicas=1
```

Delete removes the chunks and leaves a metadata marker: 3 messages remain (the chunk and metadata of `small.txt`, and the marker for `report.bin`). `replicas=1` is a hint for the next post: this bucket lives on one server only.

## Where KV and Object Store fall short

- This is not a database: no queries, no transactions across keys, only per-key revisions. Treat it as small shared state.
- In this demo, TTL is a bucket setting, so use one bucket per lifetime (locks, sessions, config).
- Values go through normal NATS messages, so the server's maximum payload (1 MB by default, according to the NATS docs) limits a KV value. Use the Object Store beyond that.
- The Object Store checks a digest on `Get`, but it is still chunks in a stream: mind storage limits and replicas.
- Watchers must handle the `nil` entry and delete markers, as in the output above.

## What's next

All of this ran on one embedded server. The next post, [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/), covers what changes with three servers and a real environment.
