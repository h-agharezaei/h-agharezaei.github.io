+++
date = '2027-04-13T10:00:00+03:30'
draft = false
title = 'Node.js or Go? When to use which'
description = 'Node.js or Go for a backend service? The same HTTP service built twice and compared on size, memory and crash behaviour, plus a decision table.'
contentType = 'analysis'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "go", "comparison", "backend"]
cover = { image = "/images/covers/node-vs-go-when-to-use.png", alt = "Node.js or Go? When to use which", hiddenInSingle = true }
+++

I added a bug on purpose to two copies of the same small service. In the Go copy, the bug cost one request: the server logged a stack trace and kept serving. In the Node.js copy, the client got its normal answer, and then the whole process exited. Every request after that failed, until something started the server again.

"Node.js or Go?" is the question I get most, and this last post of the series answers it with a small experiment instead of a slogan. The [previous post](/posts/node-profiling-memory-shutdown/) was about profiling, memory and shutdown. I use both languages at work, so what follows is one person's view with some evidence, not a verdict. I built the same service twice with no frameworks, in Node.js 20.13.1 and Go, following my posts on [`node:http`](/posts/node-http-server/) and [`net/http`](/posts/go-http-api-stdlib/). The code is a local demo.

> I re-ran the demo for this version of the post with Node v20.13.1 and Go 1.27.3 (the original run used Go 1.26) on one macOS arm64 laptop, with random free ports. Sizes and memory below are "measured here" in this re-run. I did not measure speed.

## The same service twice

First, two words. Work is {{< term "cpu-bound" "CPU-bound" >}} when the processor is the limit, like computing a lot of numbers. It is {{< term "io-bound" "I/O-bound" >}} when most of the time is spent waiting for something else, like another service or a disk. A web service usually does both kinds, and the two languages treat them differently.

The service has three endpoints:

- `POST /echo` returns the JSON it received. A bad body returns 400.
- `GET /primes?n=200000` sums the primes below `n` with a sieve. That is the CPU-bound job.
- `GET /slow` calls a tiny upstream service on loopback that always waits 20 ms before it answers. That is the I/O-bound job. The same upstream served both versions.

The shape of the code is the same in both. For example, the call to the upstream looks like this:

```js
const r = await fetch(upstream);
send(200, await r.json());
```

```go
resp, err := http.Get(upstream)
```

Both versions returned identical answers for my test requests (for `/primes` it was `{"n":200000,"sum":1709600813}`). Then I sent 3,000 mixed requests to each, 20 at a time, and all of them returned 200 (`ok=3000/3000` for both).

## What I counted

Here is what I measured, and only this:

| Measured here | Node | Go |
|---|---|---|
| Lines of code | 41 | 75 (gofmt style) |
| Dependencies | 0 (no `node_modules`) | 0 (no `go.sum`) |
| Shipped artifact | the app plus a Node runtime (the `node` binary here is 94,112,064 bytes) | one binary, 10,040,642 bytes |
| RSS at start | 86,016 KB | 10,944 KB |
| RSS after 3,000 requests | 107,248 KB | 18,672 KB |

RSS (resident set size) is the memory the operating system currently gives the process; I read it with `ps -o rss` from my own processes. A few notes on reading the table:

- The line counts are not a fair contest: my Node file is dense, and Go's formatter spreads code out.
- The Go binary size depends on the toolchain. The original run, with Go 1.26, gave 9,058,098 bytes; the memory numbers also move a little from run to run (the original run had 87,872 and 108,832 KB for Node, and 11,872 and 17,968 KB for Go).
- A tuned or real service will look different. These are two tiny programs.

I did not measure throughput or latency. The machine's load average was above 4 when I checked, so any number would be noise. If you need them, measure on a quiet machine with your own workload.

## What happens when it breaks

I added `GET /boom` to each service. In Go, the handler writes to a nil map, which panics. In Node, the handler replies and then throws inside a timer callback, so the error happens outside any request.

Go's server recovered the panic inside that one connection, logged a stack trace, and the next request worked. The client of `/boom` got no reply. These are the first lines of the log (the client port and goroutine number change every time, and I cut the log's timestamp):

```text
http: panic serving 127.0.0.1:51897: assignment to entry in nil map
goroutine 4297 [running]:
```

A request to `/primes?n=100` right afterwards answered `{"n":100,"sum":1060}`, and the process was still alive.

In Node, the client got its 200, and then the process printed the error and exited:

```text
file://<demo>/node/server.mjs:35
    setTimeout(() => { throw new Error('boom in a callback'); }, 0);
                       ^

Error: boom in a callback
    at Timeout._onTimeout (file://<demo>/node/server.mjs:35:30)
    ...
Node.js v20.13.1
```

(`<demo>` stands for my local demo folder, and I cut the last stack lines.) An error that is thrown with nobody to catch it ends the Node process, and with it every other request in flight.

Two caveats. I did not test a panic in a goroutine that you start yourself: `net/http` does not recover that one, and it would crash a Go program too. And Node's rule is covered in [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/): handle the error, or let a supervisor restart the process.

## Concurrency, briefly

Node runs your JavaScript on one thread, and the [event loop](/posts/node-event-loop/) interleaves work that is waiting. That suits `/slow` very well. A long `/primes` call, though, blocks everything until it ends. The answer in Node is [worker threads or cluster](/posts/node-worker-threads-cluster/). Go starts a {{< term "goroutine" "goroutine" >}} per request and spreads them over all cores, so a CPU-heavy handler occupies only its own goroutine ([Goroutines and channels in Go](/posts/go-goroutines-channels/)). I did not benchmark that difference here.

## Decision guide

This table is my own view, built from the points above and from working with both. It is opinion, not measurement:

| Factor | I lean toward |
|---|---|
| Team already knows JavaScript or TypeScript | Node.js |
| Ecosystem breadth (SDKs, tooling, front-end sharing) | Node.js |
| Static types out of the box | Go (TypeScript gives Node this too) |
| Deployment simplicity | Go, a single binary |
| CPU-bound work | Go |
| Streaming and proxying | both are good; Node streams need care with [backpressure](/posts/node-streams-backpressure/) |
| Many long-lived connections | both work; Go is simpler to reason about |

## Where this comparison falls short

- **It is opinion.** The numbers come from one machine and one tiny service, and the table is my view.
- **Startup memory is not production memory.** What a service uses under your real load is a different question.
- **Language is rarely the deciding factor.** Database, network and design quality usually matter more.
- **People matter more than benchmarks.** What your team already knows well usually decides faster than any number.
- **Versions change results.** Pin the Node and Go versions in your own comparison; as the binary size above shows, even the toolchain version moves numbers.

## What's next

This is the last post of the Node.js series. The blog's other series carry on, including Software Engineering, Algorithms and Distributed Systems.
