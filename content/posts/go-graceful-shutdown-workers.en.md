+++
date = '2026-12-16T10:00:00+03:30'
draft = false
title = 'Graceful shutdown for Go workers'
description = 'Graceful shutdown for a Go JetStream worker: SIGTERM with signal.NotifyContext, finishing in-flight messages, a shutdown timeout and Drain.'
contentType = 'engineering'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "shutdown", "context", "signals"]
cover = { image = "/images/covers/go-graceful-shutdown-workers.png", alt = "Graceful shutdown for Go workers", hiddenInSingle = true }
+++

Picture a worker that is halfway through a three-second job when you deploy a new version. The deploy tool tells the old worker to stop and starts a new one. What happens to the job that was running? If the old worker just dies, the job is cut in half, and nobody ever confirms it as done. It will be handed out again later. As the [previous post](/posts/nats-jetstream-idempotency/) noted, this is the most common way to meet duplicate work.

This post is about doing better: a {{< term "graceful-shutdown" "graceful shutdown" >}}, where the worker is told to stop, quits taking new jobs, finishes the ones it has, and only then exits. I first reproduce the problem with real signals, then fix it, then look at what happens when the jobs take too long. If `context` is new to you, read [sync, select and context](/posts/go-sync-select-context/) first.

> Everything ran on Go 1.26 with an embedded `nats-server` v2.15.1 and `nats.go` v1.54.0. The code is a local example, not a published repo. The times and process IDs in the outputs below vary from run to run.

## What we are testing

First, a few words about the pieces, so the outputs make sense.

A **signal** is a small message that the operating system, or another process, sends to a running process. `Ctrl+C` sends `SIGINT`. A deploy tool usually sends {{< term "sigterm" "SIGTERM" >}}, the polite "please stop" signal, and a program is allowed to catch it and clean up first. If the program does not stop in time, the tool sends `SIGKILL`, which cannot be caught and ends the process immediately.

On the NATS side, the demo uses JetStream, as in the earlier posts of the series. Messages are stored in a **stream** called `JOBS`. A worker reads them through a **consumer**. After the worker has done a job it must send an **ack** (acknowledgement) to tell the server "this one is done". If the server does not receive the ack within `AckWait`, here 5 seconds, it assumes the worker died and delivers the message again. That redelivery is the safety net, and it is also where duplicates come from.

To send real signals, the demo is one built binary with two modes, each in its own process. `server` starts an embedded server, creates the stream `JOBS` and a consumer with `AckWait` of 5 seconds, publishes two jobs (`job-1` and `job-2`), and prints the consumer's state whenever it changes. The worker modes (`naive` and `graceful`) read jobs and handle them. I send `kill -TERM <pid>` from a shell script. In the logs, the time is wall-clock and the number in brackets is the process ID.

## The naive worker

The first worker is as simple as it gets. It fetches one message, does 3 seconds of work, then acks. There is no signal handling. I sent `SIGTERM` one second after it started, then started a new worker (output shortened):

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

Let us read it. The first worker (`78489`) starts `job-1`. The server line right after says one message is pending (`job-2`, not yet fetched) and one is being worked on (`ackPending=1`). Then I send the signal, and the worker exits with status 143.

Without a handler, Go's default for `SIGTERM` is to terminate the process, so the job was cut in half and never acked. Exit status 143 is 128 plus the signal number, 15. The new worker (`78620`) starts at 40.9, takes `job-2` first and acks it. Then it receives `job-1` again, now marked `delivery #2`: the server held `job-1` as pending until `AckWait` ran out (from 38.9 to 43.9, five seconds) and only then redelivered it. Nothing was lost, but the job ran twice, and it was five seconds late.

## Catch the signal with a context

To change this, the worker must notice the signal instead of dying. `signal.NotifyContext` returns a context that is cancelled when one of the listed signals arrives:

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
```

Now the signal no longer kills the process. It just closes `ctx.Done()`, a channel we can watch. What we do next is up to us, and that is the whole point.

## The shutdown sequence

The core idea is simple: **stop taking new work, finish the work in hand, make sure it is acknowledged, then leave**. And to avoid waiting forever on a stuck job, put a time limit on the waiting. In order:

1. Stop fetching new messages.
2. Wait for in-flight handlers, but only up to a limit.
3. Make sure the acks were sent.
4. `nc.Drain()`, then exit.

Here is the worker loop and the shutdown code:

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

How it works: the `for` loop keeps fetching one message at a time, and `ctx.Err() == nil` turns false once the signal has arrived, so the loop ends by itself. Each message is handled in its own goroutine, and a `sync.WaitGroup` (`wg`) counts the running handlers. After the loop, a helper goroutine waits for the counter to reach zero and closes the channel `done`. The `select` then waits for whichever comes first: `done` (all jobs finished) or the timeout `shutCtx` (the grace period ran out).

Two details are easy to miss. The handlers get `jobCtx`, not `ctx`: the signal itself must not cancel work that we want to finish, only the timeout should. And `AckSync` waits for the server's confirmation, so the ack is not still sitting in a buffer when we exit. `Drain` then lets the connection flush and close properly.

Now a run with a 10 second shutdown timeout and `SIGTERM` one second after start. Both jobs take 3 seconds and run concurrently:

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

Both jobs started at 54.8 and the signal came a second later. The worker logged that it would fetch no more, but it did not die: it waited until 57.8, when both jobs were done and acked, which is the original 3 seconds counted from the start. Then it drained and exited with status 0. The server line at the end shows `redelivered=0` and nothing pending. A second worker I started afterwards found nothing to do. Compare this with the naive run: same signal, but no duplicate and no five-second delay.

## When the handler outlasts the timeout

A graceful shutdown cannot wait forever. Let us see what happens when the jobs take 8 seconds, but the shutdown timeout is only 1.5 seconds:

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

(The output is shortened; the second job's lines are left out, which is why the server shows two messages.) After the signal the worker waits 1.5 seconds, until 10.765. Then the timeout fires, it cancels `jobCtx`, the handler gives up (`context canceled`) and does not ack, and the process exits with code 1. The messages came back as delivery #2 when `AckWait` expired (08.3 + 5s = 13.3), and the new worker took them.

So a graceful shutdown is not a guarantee. It only shrinks the window in which a job can be cut off. The idempotent handler from the last post is still needed.

## Exit codes and Kubernetes

A non-zero exit code tells whoever supervises the process that shutdown was not clean, which is why I return 1 on timeout. In Kubernetes, as I understand the documented behavior, a pod gets `SIGTERM`, and after `terminationGracePeriodSeconds` it gets `SIGKILL`, which cannot be caught. I did not run Kubernetes here, and I am not stating any default value. The rule I take from it: set the shutdown timeout lower than the grace period, and the grace period longer than your slowest normal job.

## Shutdown traps

- **A long `MaxWait` slows the shutdown.** `Fetch` with `MaxWait` means the loop notices the signal within a second at worst. Keep the wait short.
- **Do not pass the signal context into handlers if you want them to finish.** Use a separate context that only the timeout cancels.
- **Long handlers must check their context.** Otherwise the timeout cannot stop them, and the `wg.Wait()` after it blocks.
- **`SIGKILL` skips all of this.** Graceful shutdown reduces redelivery, it does not remove it.
- **Other servers need the same care.** If the process also serves HTTP, shut that down in the same sequence.

## What's next

The worker now stops properly, but when something goes wrong we still mostly guess. "Observability for JetStream: metrics, logs and traces" is about replacing that guessing with data.
