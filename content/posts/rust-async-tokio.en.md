+++
date = '2027-01-11T10:00:00+03:30'
draft = false
title = 'async/await and Tokio in Rust'
description = 'Rust async/await and Tokio: lazy futures, spawn, join!, select!, timeouts, cancellation, async Mutex and why blocking calls hurt, with real output.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "tokio", "intermediate"]
cover = { image = "/images/covers/rust-async-tokio.png", alt = "async/await and Tokio in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-concurrency-threads/) we used OS threads. Threads are fine for a handful of workers, but a server that waits on thousands of sockets does not want one thread per wait. That is what **async** is for: many tasks share a few threads and yield while they wait. As a Go developer I kept comparing it to goroutines, so I will do that at the end, carefully.

> Everything below was compiled and run with Rust 1.90 and `tokio` 1.54.1 (feature `full`). The timings are measured on my laptop with a 1-minute load average around 2, so read them as rough.

## A future does nothing until it is awaited

An `async fn` returns a **Future** immediately; its body does not start. Rust has no built-in executor, so you need a runtime crate. `#[tokio::main]` sets one up around `main`.

```rust
async fn greet(name: &str) -> String {
    println!("greet is running");
    tokio::time::sleep(Duration::from_millis(50)).await;
    format!("hello {name}")
}

#[tokio::main]
async fn main() {
    let fut = greet("Roham"); // nothing printed yet
    println!("future created");
    let msg = fut.await;      // now the body runs
    println!("{msg}");

    greet("ignored");         // never awaited
    println!("done");
}
```

```text
warning: unused implementer of `Future` that must be used
  --> src/main.rs:16:5
   |
16 |     greet("ignored"); // never awaited: the body never runs
   |     ^^^^^^^^^^^^^^^^
   = note: futures do nothing unless you `.await` or poll them

future created
greet is running
hello Roham
done
```

"greet is running" appears only after `fut.await`, and the ignored call never prints at all. The compiler warns about it, which is a good thing to remember when something silently does not happen.

## spawn and join!

`tokio::spawn` starts a future as an independent task and returns a **JoinHandle**; awaiting it gives `Result<T, JoinError>`. `tokio::join!` instead runs several futures concurrently inside the current task. I ran three jobs of 200 ms each, first awaited one after another, then with `join!`:

```rust
let (a, b, c) = tokio::join!(job(1, 200), job(2, 200), job(3, 200));
```

```text
spawned result = 10
sequential: (10, 20, 30) in 607.132ms
join!:      (10, 20, 30) in 201.520583ms
```

Measured: the sum for the sequential version, roughly the maximum for `join!`.

## select!, timeouts and cancellation

`tokio::select!` waits for the first branch to complete and **drops** the others. Dropping a future is how you cancel it: it simply never runs again, and its locals are destroyed. A `Drop` print makes this visible:

```rust
tokio::select! {
    r = slow("fast", 50)  => println!("winner: {r}"),
    r = slow("slow", 500) => println!("winner: {r}"),
}
tokio::select! {
    r = slow("work", 500) => println!("got {r}"),
    _ = sleep(Duration::from_millis(100)) => println!("timed out"),
}
match timeout(Duration::from_millis(100), slow("job", 500)).await {
    Ok(v) => println!("ok {v}"),
    Err(e) => println!("error: {e} / {e:?}"),
}
```

```text
fast finished
fast dropped
slow dropped
winner: fast
work dropped
timed out
job dropped
error: deadline has elapsed / Elapsed(())
```

"slow finished" never prints: the loser was cancelled at its `.await`. `tokio::time::timeout` wraps the same idea and returns `Err(Elapsed)`. This is the Rust counterpart of `select` with `time.After` and `context` in the [Go post on sync, select and context](/posts/go-sync-select-context/), except that cancellation here needs no token: dropping is enough.

## Channels and the two Mutexes

`tokio::sync::mpsc` is the async channel. Three producer tasks sent three numbers each and one consumer added them under a `tokio::sync::Mutex`:

```text
received 9 messages: [100, 101, 102, 200, 201, 202, 300, 301, 302]
total = 1809
```

The consumer holds the async guard across an `.await` (a `yield_now`), which is allowed. With `std::sync::Mutex` the same code is rejected, because a task may resume on another thread and `MutexGuard` is not `Send`:

```text
error: future cannot be sent between threads safely
  = help: ... the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
 10 |         tokio::task::yield_now().await; // guard still alive across await
    |                                  ^^^^^ await occurs here, with `mut g` maybe used later
```

If you never hold the lock across an `.await`, the std mutex is fine and cheaper.

## Do not block the runtime

On a `current_thread` runtime one thread runs every task. A ticker task wants to print every 100 ms, while `main` calls `std::thread::sleep` for 500 ms:

```text
blocking sleep done at 501.031667ms
tick at 602.285833ms
tick at 704.401542ms
tick at 805.714833ms
--- with spawn_blocking ---
tick at 102.785208ms
tick at 204.127ms
tick at 305.928916ms
blocking result 42 at 506.208291ms
```

The blocking sleep froze the ticker completely; the first tick came only after it ended. Moving the same sleep into `tokio::task::spawn_blocking` (a separate thread pool) kept the ticks on schedule.

## Compared with Go goroutines

Certain facts only. Go's scheduler is part of the language runtime, so `go f()` just works; in Rust, async needs a runtime crate such as Tokio. Async functions are "colored": an `async fn` can only be awaited from async code, so the choice spreads through your call graph, while a Go function can be called from a goroutine or not without any change to its signature.

## A few things to watch

- Forgetting `.await` compiles with only a warning; read warnings.
- Cancellation happens at `.await` points, so cleanup belongs in `Drop`, not after an await.
- A std `MutexGuard` held across `.await` makes the future `!Send`, which `tokio::spawn` rejects.
- Never call blocking code (`thread::sleep`, heavy CPU, sync file or DB drivers) directly in a task; use `spawn_blocking`.
- `join!` is concurrency inside one task; use `spawn` when you want other threads to help.

## Exercise

1. Write `async fn fetch(id: u32) -> u32` that sleeps 100 ms, then run ten of them with `spawn` and collect the results through their `JoinHandle`s.
2. Wrap one of them in `tokio::time::timeout` of 50 ms and print the error.
3. Run a CPU loop on a `current_thread` runtime beside a ticker, then move it to `spawn_blocking`.

## What's next

Next is Serde and JSON in Rust: serializing and deserializing structs the way we did with `encoding/json` in Go.
