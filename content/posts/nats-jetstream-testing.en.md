+++
date = '2027-01-17T10:00:00+03:30'
draft = false
title = 'Testing JetStream services with an embedded nats-server'
seoTitle = 'Testing JetStream with an Embedded nats-server'
description = 'Test JetStream consumers in plain go test: an embedded nats-server per test, no sleeps, short BackOff, covering retry, DLQ and idempotency.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "testing", "messaging"]
cover = { image = "/images/covers/nats-jetstream-testing.png", alt = "Testing JetStream services with an embedded nats-server", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/nats-jetstream-observability/) we looked at how to see what a JetStream service is doing in production. This post is about seeing it before production. Over the last posts we described behaviors: [retry and dead-letter queues](/posts/nats-jetstream-retry-dlq/) and [idempotency](/posts/nats-jetstream-idempotency/). Each of them was verified by a throwaway program that I read by eye. Here we turn those checks into real tests with [`go test`](/posts/go-testing-basics/), no Docker and no external server, that fail loudly when someone breaks the behavior.

> Everything ran on Go 1.26 with `nats-server` v2.15.1 and `nats.go` v1.54.0. The outputs are from my machine.

## What we test

A small `worker` package with four parts: `Setup` creates the stream, a `DLQ` stream and a consumer with `MaxDeliver: 3` and a `BackOff`; `Run` pulls messages and acks only when the handler returns nil; `RunDLQ` listens to the max-deliveries advisory and copies the message to the DLQ stream (as in the retry post); and `Ledger` is an idempotent handler that applies each order ID once. The tests need a real JetStream, and the simplest way is to start one inside the test process.

## The two helpers

```go
func newTestServer(t *testing.T) *server.Server {
	t.Helper()
	s, err := server.NewServer(&server.Options{
		Host: "127.0.0.1", Port: -1, // random free port
		JetStream: true, StoreDir: t.TempDir(),
		NoLog: true, NoSigs: true,
	})
	if err != nil {
		t.Fatal(err)
	}
	go s.Start()
	if !s.ReadyForConnections(5 * time.Second) {
		t.Fatal("nats-server not ready")
	}
	t.Cleanup(func() { s.Shutdown(); s.WaitForShutdown() })
	return s
}

func connect(t *testing.T, s *server.Server) (*nats.Conn, nats.JetStreamContext) {
	t.Helper()
	nc, err := nats.Connect(s.ClientURL())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(nc.Close)
	js, _ := nc.JetStream()
	return nc, js
}
```

`Port: -1` means a random free port, so tests never collide with each other or with a NATS running on your laptop. `t.TempDir()` gives each server its own store that Go deletes afterwards, and `t.Cleanup` shuts everything down in reverse order. Every test gets a fresh server, so no test can see another test's streams.

## No sleeps: wait for a condition

A fixed `time.Sleep` is either too short (flaky) or too long (slow). Instead I wrote a tiny helper that polls a condition until a deadline, and I poll state the server already exposes: `StreamInfo` and `ConsumerInfo`.

```go
func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(2 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", what)
}

// true when the consumer acked everything up to stream sequence seq
func acked(js nats.JetStreamContext, seq uint64) bool {
	ci, err := js.ConsumerInfo(Stream, Consumer)
	return err == nil && ci.AckFloor.Stream >= seq && ci.NumAckPending == 0
}
```

The 2 ms sleep is only the polling interval; the test continues the moment the condition holds, and the 3 s deadline is a failure limit, not a wait. Handlers record what happened (for example `NumDelivered`) into a mutex-protected slice, and the test asserts on it after the ack.

## Fast tests: shrink the time

Production values like `AckWait: 30s` would make a retry test take a minute. The consumer config comes from a `Config`, so tests pass tiny values:

```go
var testCfg = Config{
	MaxDeliver: 3,
	AckWait:    200 * time.Millisecond,
	BackOff:    []time.Duration{20 * time.Millisecond, 50 * time.Millisecond},
}
```

Because the worker does not ack on failure, the server redelivers following `BackOff`, so the second and third attempts come after 20 ms and 50 ms. Design the code so these durations are parameters; otherwise you cannot test it quickly.

## The tests

Retry then success: the handler fails twice and succeeds on the third delivery.

```go
func TestRetryThenSuccess(t *testing.T) {
	var d deliveries
	js := start(t, func(_ context.Context, m *nats.Msg) error {
		if d.add(m) < 3 {
			return errors.New("temporary failure")
		}
		return nil
	})
	js.Publish(Subject, []byte("flaky"))
	waitFor(t, "ack after retries", func() bool { return acked(js, 1) })

	if got := d.list(); len(got) != 3 || got[2] != 3 {
		t.Fatalf("deliveries = %v, want [1 2 3]", got)
	}
}
```

The poison message test waits for the DLQ stream to have a message, then asserts that it has exactly one, that the handler ran exactly `MaxDeliver` times, and that the payload is intact. The duplicate-publish test publishes twice with the same `nats.MsgId` and checks `Duplicate` in the second `PubAck` and one message in the stream. The crash test uses a handler that applies the side effect through `Ledger` and then returns an error on the first delivery, simulating a crash before the ack; after the redelivery the balance must still be 100. The happy path test is the same shape as retry, with one delivery.

## Real run

```
$ go test ./... -v
--- PASS: TestHappyPath (0.13s)
--- PASS: TestRetryThenSuccess (0.18s)
--- PASS: TestPoisonMessageGoesToDLQ (0.24s)
--- PASS: TestDuplicatePublishStoredOnce (0.05s)
--- PASS: TestRedeliveryAfterCrashIsSkipped (0.14s)
ok  	jstest/worker	1.125s
```

Five tests, each with its own server, finish in about a second. I ran `go test -race -count=3` (3.6 s) and later `-count=10` (8.6 s), and all passed with no race reports. The machine was busy (load average 6 to 10), so treat the times as rough.

To check the tests can fail, I copied the project and disabled the dedup check in `Ledger` (`if false && l.seen[o.ID]`):

```
--- FAIL: TestRedeliveryAfterCrashIsSkipped (0.13s)
    worker_test.go:227: balance = 200, want 100
FAIL
FAIL	jstest/worker	1.083s
```

That is the double-apply bug from the idempotency post, now caught in about a second.

## A few things to watch

- Always call `nc.Flush()` after subscribing to the advisory, as `RunDLQ` does; otherwise the test can publish before the server knows the subscription.
- `ReadyForConnections` must come before connecting, and `Cleanup` order matters: stop the worker before closing the connection and server.
- Gate slower tests (real timeouts, bigger data) with `testing.Short()` so `go test -short` stays instant.
- Absence is hard to prove without waiting: "no second DLQ message" rests on the `MsgId` and on counting handler calls, not on a long sleep.
- An embedded single server does not test clustering, auth or real network failures.

## What's next

Next: KV and Object Store in NATS, where JetStream becomes a key-value store and a blob store.
