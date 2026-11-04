+++
date = '2027-01-17T10:00:00+03:30'
draft = false
title = 'Testing JetStream services with an embedded nats-server'
seoTitle = 'Testing JetStream with an Embedded nats-server'
description = 'Test JetStream consumers in plain go test: an embedded nats-server per test, no sleeps, short BackOff, covering retry, DLQ and idempotency.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "testing", "messaging"]
cover = { image = "/images/covers/nats-jetstream-testing.png", alt = "Testing JetStream services with an embedded nats-server", hiddenInSingle = true }
+++

Imagine you change one line in a retry handler and, a week later, a customer is charged twice. Nothing in the old checks would have caught it. Each JetStream behavior in this series, from [retry and dead-letter queues](/posts/nats-jetstream-retry-dlq/) to [idempotency](/posts/nats-jetstream-idempotency/), was verified by a throwaway program whose output I read by eye. That shows it worked once, on the day I ran it. It does not stop anyone from breaking it later.

The [previous post](/posts/nats-jetstream-observability/) was about seeing what a service does in production. Here we turn those eyeball checks into real tests with [`go test`](/posts/go-testing-basics/): no Docker, no external server, and tests that fail loudly when someone breaks the behavior.

The core idea is short. A JetStream service needs a real JetStream server to test against, and `nats-server` is a Go library. So each test starts its own private server inside the test process, on a random port, with a temporary directory, and throws it away when the test ends. No mocks of NATS, no shared state between tests.

> Everything ran with Go 1.27, `nats-server` v2.15.1 and `nats.go` v1.54.0, on my machine. The code is a local example, not a published repo. The test times below vary from run to run.

## What we test

The code under test is a small `worker` package with four parts:

- `Setup` creates the work stream, a second stream called `DLQ` (a {{< term "dlq" "dead-letter queue" >}} for messages that keep failing) and a consumer. The consumer allows at most three deliveries (`MaxDeliver: 3`) and waits a configurable time between attempts (`BackOff`).
- `Run` pulls messages one at a time and sends an ack only when the handler returns no error. If the handler fails, there is no ack, and the server delivers the message again after the backoff time.
- `RunDLQ` listens to the server's "max deliveries reached" advisory and copies the message to the `DLQ` stream, as in the retry post.
- `Ledger` is an {{< term "idempotency" "idempotent" >}} handler: it adds an order's amount to a balance only the first time it sees that order ID.

If these terms are new, the earlier posts in the series explain them. What matters here is that all of this behavior lives in the server and the client together, so a test needs a real JetStream. The simplest way is to start one inside the test.

## The two helpers

Every test needs a server and a connection to it. These two helpers do that:

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

Some details worth knowing:

- `Port: -1` means "pick a random free port". Tests never collide with each other, or with a NATS that is already running on your laptop. The host is `127.0.0.1`, so nothing is reachable from outside.
- `t.TempDir()` gives each server its own store directory, and Go deletes it when the test ends.
- `t.Cleanup` runs the registered functions in reverse order, so the connection closes first and the server shuts down last.
- `NoSigs: true` stops the server from installing its own signal handlers, which a test binary does not want.
- Every test gets a fresh server, so no test can see another test's streams.

## No sleeps: wait for a condition

Now the part that makes async tests flaky. A test publishes a message, and the worker handles it some milliseconds later. How does the test know when to check? With a fixed `time.Sleep`, the sleep is either too short (the test fails sometimes, a {{< term "flaky-test" "flaky test" >}}) or too long (the suite is slow).

The fix is to wait for a condition instead of a time. I wrote a tiny helper that checks a condition every few milliseconds until a deadline. And the thing it checks is state the server already exposes: `StreamInfo` and `ConsumerInfo`.

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

`acked` reads two things from `ConsumerInfo`. `AckFloor.Stream` is the highest stream sequence below which everything has been acknowledged, and `NumAckPending` is how many messages are delivered but not yet acknowledged. When the floor has reached our message and nothing is pending, the message is fully done.

The 2 ms sleep is only the polling interval. The test continues the moment the condition becomes true, and the 3 s deadline is a limit for failure, not a wait. In the passing case the test takes as long as the work takes and no longer.

The handlers in the tests record what they saw (for example `NumDelivered`, the delivery attempt number) into a slice protected by a mutex, and the test checks that slice after the ack.

## Fast tests: shrink the time

There is a second time problem. A production consumer might have `AckWait: 30s`, and a retry test would then take a minute. So the consumer settings come from a `Config` value, and tests pass tiny durations:

```go
var testCfg = Config{
	MaxDeliver: 3,
	AckWait:    200 * time.Millisecond,
	BackOff:    []time.Duration{20 * time.Millisecond, 50 * time.Millisecond},
}
```

Because the worker does not ack on failure, the server redelivers following `BackOff`: the second attempt comes about 20 ms after the first, and the third about 50 ms after the second. Note that I did not fake the clock. I only made the real waiting short. The lesson is about design: make these durations parameters. If they are constants buried in the code, you cannot test the retry path quickly.

## The tests

The first test covers the retry path: the handler fails twice and succeeds on the third delivery. The assertion checks the delivery numbers the handler saw.

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

`start` sets up the stream and consumer, runs the worker and the DLQ listener, and registers cleanup. The test publishes one message, waits until it is acked, and then checks that the handler ran three times with delivery numbers 1, 2, 3. (The real test also checks every element and that the DLQ is empty; I shortened it here.)

The other four tests follow the same shape:

- **Happy path:** one delivery, one ack, nothing in the DLQ.
- **Poison message:** the handler always fails. The test waits for the DLQ stream to hold a message, then asserts that there is exactly one, that the handler ran exactly `MaxDeliver` times, and that the payload arrived intact.
- **Duplicate publish:** it publishes twice with the same `nats.MsgId` and checks that the second `PubAck` says `Duplicate` with the same sequence, and that the stream holds one message.
- **Redelivery after a crash:** the handler applies the side effect through `Ledger` and then returns an error on the first delivery, simulating a crash before the ack. After the redelivery the balance must still be 100, not 200.

## Real run

`go test ./... -v` prints one line per test:

```text
=== RUN   TestHappyPath
--- PASS: TestHappyPath (0.11s)
=== RUN   TestRetryThenSuccess
--- PASS: TestRetryThenSuccess (0.22s)
=== RUN   TestPoisonMessageGoesToDLQ
--- PASS: TestPoisonMessageGoesToDLQ (0.22s)
=== RUN   TestDuplicatePublishStoredOnce
--- PASS: TestDuplicatePublishStoredOnce (0.05s)
=== RUN   TestRedeliveryAfterCrashIsSkipped
--- PASS: TestRedeliveryAfterCrashIsSkipped (0.12s)
PASS
ok  	jstest/worker	1.117s
```

Five tests, each with its own server, finish in about a second. The numbers in parentheses are the time per test. They vary from run to run, and the machine was busy while I ran this, so treat them as rough. I also ran `go test -race -count=3`, which repeats the whole suite three times with Go's race detector on, and it passed with no race reports (the original run also did `-count=10`).

A test is only worth something if it can fail. To check, I copied the project and disabled the dedup check in `Ledger` by changing the condition to `if false && l.seen[o.ID]`:

```text
--- FAIL: TestRedeliveryAfterCrashIsSkipped (0.13s)
    worker_test.go:227: balance = 200, want 100
FAIL
FAIL	jstest/worker	1.126s
```

That is exactly the double-apply bug from the idempotency post: the message was processed twice and the balance doubled. The suite now catches it in about a second. The other tests still pass, because they do not depend on the ledger.

## Traps in JetStream tests

- Call `nc.Flush()` after subscribing to the advisory, as `RunDLQ` does. Otherwise the test can publish before the server knows about the subscription, and the advisory is lost.
- `ReadyForConnections` must come before connecting. The `Cleanup` order matters too: stop the worker first, then close the connection and the server. Otherwise the worker may still be using a connection or a server that is already gone.
- Gate slower tests (real timeouts, bigger data) with `testing.Short()`, so `go test -short` stays instant.
- Absence is hard to prove without waiting. "There is no second DLQ message" rests on the `MsgId` (the server drops the duplicate) and on counting handler calls, not on a long sleep.
- An embedded single server does not test clustering, auth or real network failures. For those you need other tests, or the failure testing ideas from [Failure testing with fault injection](/posts/ds-fault-injection-testing/).

## What's next

The next post, [KV and Object Store in NATS](/posts/nats-kv-object-store/), keeps the same embedded server and shows that JetStream can also be a key-value store and a blob store.
