+++
date = '2026-12-16T10:00:00+03:30'
draft = false
title = 'Graceful shutdown for Go workers'
description = 'Graceful shutdown for a Go JetStream worker: SIGTERM with signal.NotifyContext, finishing in-flight messages, a shutdown timeout and Drain.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "shutdown", "context", "signals"]
cover = { image = "/images/covers/go-graceful-shutdown-workers.png", alt = "Graceful shutdown for Go workers", hiddenInSingle = true, hiddenInList = true }
+++

The [previous post](/posts/nats-jetstream-idempotency/) ended by saying that redelivery during a deploy is the most common way to hit duplicates. A deploy sends your worker a signal and starts a new one. If the old one just dies, whatever it was doing is redelivered later. In this post I test that with real signals and then fix it. If `context` is new to you, read [sync, select and context](/posts/go-sync-select-context/) first.

> Everything ran on Go 1.26 with an embedded `nats-server` v2.15.1 and `nats.go` v1.54.0. To send real signals, the demo is one built binary with two modes: `server` (embedded server, a stream `JOBS`, a consumer with `AckWait` of 5 seconds, two published jobs) and `worker`, each in its own process. I send `kill -TERM <pid>` from a shell script. The times are wall-clock, and the number in brackets is the PID.

## The naive worker

It fetches one message, does 3 seconds of work, then acks. There is no signal handling. I sent `SIGTERM` one second after it started, then started a new worker (output shortened):

```
23:41:38.900 [78489] start  job-1 (delivery #1), takes 3s
23:41:38.949 [78388] server: consumer pending=1 ackPending=1 redelivered=0
--- kill -TERM 78489
worker exit status: 143
23:41:40.918 [78620] start  job-2 (delivery #1), takes 3s
23:41:43.920 [78620] acked  job-2
23:41:43.920 [78620] start  job-1 (delivery #2), takes 3s
23:41:43.959 [78388] server: consumer pending=0 ackPending=1 redelivered=1
23:41:46.925 [78620] acked  job-1
```

Without a handler, Go's default behavior for `SIGTERM` is to terminate the process, so the job was cut in half and never acked. The server held it as pending until `AckWait` ran out (38.9 to 43.9, five seconds) and then redelivered it as delivery #2. Exit status 143 is 128 plus the signal number, 15. Nothing was lost, but the job ran twice and was late.

## Catch the signal with a context

`signal.NotifyContext` returns a context that is cancelled when one of the listed signals arrives:

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
```

Now the signal no longer kills the process; it just closes `ctx.Done()`. What we do next is up to us, and that is the whole point.

## The shutdown sequence

The order matters:

1. Stop fetching new messages.
2. Wait for in-flight handlers, but only up to a limit.
3. Make sure the acks were sent.
4. `nc.Drain()`, then exit.

```go
for ctx.Err() == nil { // stop fetching once the signal arrives
    msgs, err := sub.Fetch(1, nats.MaxWait(time.Second))
    if err != nil {
        continue
    }
    m := msgs[0]
    wg.Add(1)
    go func() {
        defer wg.Done()
        if err := handle(jobCtx, m, work); err != nil {
            return // not acked, will be redelivered
        }
        m.AckSync()
    }()
}

shutCtx, cancel := context.WithTimeout(context.Background(), grace)
defer cancel()
done := make(chan struct{})
go func() { wg.Wait(); close(done) }()
select {
case <-done:
case <-shutCtx.Done():
    cancelJobs() // jobCtx: ask handlers to give up
    wg.Wait()
    code = 1
}
nc.Drain()
os.Exit(code)
```

Two details. The handlers get `jobCtx`, not `ctx`: the signal must not cancel work that we want to finish, only the timeout does. And `AckSync` waits for the server's confirmation, so the ack is not still in a buffer when we exit. `Drain` then lets the connection flush and close properly.

With a 10 second shutdown timeout and `SIGTERM` one second after start (both jobs take 3 seconds and run concurrently):

```
23:41:54.845 [79434] start  job-1 (delivery #1), takes 3s
23:41:54.845 [79434] start  job-2 (delivery #1), takes 3s
--- kill -TERM 79434
23:41:55.845 [79434] signal received, no more fetching; waiting for in-flight jobs
23:41:57.846 [79434] acked  job-1
23:41:57.846 [79434] acked  job-2
23:41:57.846 [79434] all in-flight jobs finished
23:41:57.846 [79434] drained, exit code 0
worker exit status: 0
23:41:57.862 [79388] server: consumer pending=0 ackPending=0 redelivered=0
```

The jobs finished and were acked after the signal, the process exited with 0, and the server shows `redelivered=0` and nothing pending. A second worker I started afterwards found nothing to do.

## When the handler outlasts the timeout

Now the jobs take 8 seconds and the shutdown timeout is 1.5 seconds:

```
23:42:08.264 [80234] start  job-1 (delivery #1), takes 8s
--- kill -TERM 80234
23:42:09.264 [80234] signal received, no more fetching; waiting for in-flight jobs
23:42:10.765 [80234] shutdown timeout: true, cancelling jobs
23:42:10.765 [80234] abort  job-1: context canceled (not acked)
23:42:10.766 [80234] drained, exit code 1
23:42:13.266 [80428] start  job-1 (delivery #2), takes 1s
23:42:13.309 [80227] server: consumer pending=0 ackPending=2 redelivered=2
```

The worker gave up on time, did not ack, and exited with code 1. The messages came back as delivery #2 when `AckWait` expired (08.3 + 5s), so a graceful shutdown is not a guarantee: it only shrinks the window. The idempotent handler from the last post is still needed.

## Exit codes and Kubernetes

A non-zero exit code tells whoever supervises the process that shutdown was not clean, which is why I return 1 on timeout. In Kubernetes, as I understand the documented behavior, a pod gets `SIGTERM`, then after `terminationGracePeriodSeconds` it gets `SIGKILL`, which cannot be caught. I did not run Kubernetes here, and I am not stating any default value. The rule I take from it: set the shutdown timeout lower than the grace period, and the grace period longer than your slowest normal job.

## A few things to watch

- `Fetch` with `MaxWait` means the loop notices the signal within a second at worst. Keep the wait short.
- Do not pass the signal context into handlers if you want them to finish. Use a separate context that only the timeout cancels.
- Make long handlers check their context, otherwise the timeout cannot stop them and `wg.Wait()` after it blocks.
- `SIGKILL` skips all of this. Graceful shutdown reduces redelivery, it does not remove it.
- If the process also serves HTTP, shut that down in the same sequence.

## What's next

The worker now stops properly, but when something goes wrong we still mostly guess. The next post covers observability for JetStream: metrics, logs and traces.
