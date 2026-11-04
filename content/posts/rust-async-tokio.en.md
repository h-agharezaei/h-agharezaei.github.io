+++
date = '2027-01-11T10:00:00+03:30'
draft = false
title = 'async/await and Tokio in Rust'
description = 'Rust async/await and Tokio: lazy futures, spawn, join!, select!, timeouts, cancellation, async Mutex and why blocking calls hurt, with real output.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "tokio", "intermediate"]
cover = { image = "/images/covers/rust-async-tokio.png", alt = "async/await and Tokio in Rust", hiddenInSingle = true }
+++

Think of a server that has ten thousand open connections. Almost all of them are doing nothing at any moment: each one is waiting for the other side to send a byte or for the database to answer. If you give every connection its own operating-system thread, as in the [previous post](/posts/rust-concurrency-threads/), you have ten thousand threads that spend nearly all their time asleep, and each thread costs memory and scheduling work. It is a bit like hiring one waiter per table, and each waiter stands at the table until the food is ready.

**Async** is the other approach: a waiter takes care of many tables, and while one table is waiting for its food, he walks to another. In program terms, many tasks share a few threads, and a task that has to wait steps aside so the thread can run another task. As a Go developer I kept comparing this with goroutines, and I do that at the end, carefully.

This post starts with the one idea that surprises everybody (an async function does nothing until you await it), then covers running several tasks together, cancelling them, sharing data between them, and the one big mistake to avoid: blocking the thread.

> Everything below was compiled and run with Rust 1.90 and `tokio` 1.54.1 (feature `full`). I re-ran every demo for this version of the post and the outputs match. The timings (in the `join!` and blocking sections) are the numbers from the original run, which I recorded on my laptop with a 1-minute load average around 2; my re-run happened on a busier machine and gave the same shape with slightly different milliseconds, so read all timings as rough. Programs that print from several tasks can print in a different order. I removed the "For more information..." lines and the `note:` lines that point into my home directory.

## A future does nothing until it is awaited

Put the word `async` in front of a function and its meaning changes. Calling it no longer runs the body. It returns a **future**, a value that stands for "work that has not been done yet". The body runs only when someone awaits that future with `.await`. Think of a future as a written order: nothing is cooked until the kitchen picks it up.

Rust's standard library does not include the "kitchen" that runs futures, called an **executor** or **runtime**, so you add a crate for it. {{< term "tokio" "Tokio" >}} is the most common one. The attribute `#[tokio::main]` sets a Tokio runtime up around `main` so that `main` itself can be `async`. Here is a small program that makes the laziness visible:

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
   |
   = note: futures do nothing unless you `.await` or poll them
   = note: `#[warn(unused_must_use)]` on by default

future created
greet is running
hello Roham
done
```

Read the output in order. `let fut = greet("Roham")` calls the function, but "greet is running" is not printed. We get a {{< term "rust-future" "future" >}} and nothing else. So "future created" comes first. Only when we write `fut.await` does the body start: "greet is running", then the 50 ms sleep, then `hello Roham`. The last call, `greet("ignored")`, builds a future and throws it away without awaiting, so its body never runs: there is no second "greet is running". The compiler warns about this at the top (that warning is printed at compile time, before the program starts), which is worth remembering the next time something in async code silently does not happen.

What does `.await` really do? Inside an async function, `.await` means: "I cannot continue until this future is ready. If it is not ready yet, pause me and let the thread do something else, and come back when it is." The point where a task can pause is always an `.await`, and nowhere else. Code between two `.await`s runs without interruption. This is the idea behind everything that follows. (Under the hood, the runtime repeatedly asks the future "are you done?" by calling a method named `poll`; you almost never call it yourself, and a later post in this series looks at it closely.)

## spawn and join!

Awaiting futures one after another is sequential: the second starts when the first ends. To get several things going at once there are two tools. `tokio::spawn` starts a future as an independent **task** that the runtime can run on any of its threads, and returns a `JoinHandle`; awaiting the handle gives `Result<T, JoinError>` (an `Err` if the task panicked). `tokio::join!` runs several futures concurrently inside the current task and waits for all of them.

The demo has a `job` function that sleeps and returns `id * 10`. First one job through `spawn`, then three 200 ms jobs awaited one after another, then the same three with `join!`:

```rust
let (a, b, c) = tokio::join!(job(1, 200), job(2, 200), job(3, 200));
```

```text
spawned result = 10
sequential: (10, 20, 30) in 607.132ms
join!:      (10, 20, 30) in 201.520583ms
```

(The timing lines are from the original run, as I said above.) The results are the same in both. The time is not: awaiting one by one takes the sum of the waits, about 600 ms. With `join!` all three sleeps run at the same time, so the total is about the longest one, 200 ms. No extra thread was needed for that; the three waits simply overlap.

## select!, timeouts and cancellation

Often you want "whichever finishes first". `tokio::select!` waits for the first branch to complete and **drops** the others. Dropping a future is how async Rust cancels it: the future never runs again and its local variables are destroyed. This is {{< term "task-cancellation" "cancellation" >}} by drop. To see it, each `slow` job in the demo holds a small value that prints a line when it is dropped:

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

Three experiments, in order:

- In the first `select!`, `fast` (50 ms) beats `slow` (500 ms). We see "fast finished", then both values dropped, and the winner is announced. The line "slow finished" never appears: `slow` was cancelled while it was still sleeping at its `.await`, and only its drop message ran.
- In the second, the second branch is a plain 100 ms timer. The timer wins, we print "timed out", and the 500 ms `work` is cancelled ("work dropped").
- The third uses `tokio::time::timeout`, a ready-made version of the same idea. It returns `Err(Elapsed)` if the deadline passes. The slow job is again dropped, and the error prints as `deadline has elapsed`.

This is the Rust counterpart of `select` with `time.After` and `context` in the [Go post on sync, select and context](/posts/go-sync-select-context/). The difference is that cancellation here needs no token passed around: dropping the future is enough.

## Channels and the two Mutexes

Tasks, like threads, can send messages. `tokio::sync::mpsc` is the async channel: sending and receiving are `.await`-able, so a task waits without blocking its thread. In the demo three producer tasks send three numbers each, and one consumer task receives them and adds them into a total protected by a `tokio::sync::Mutex`:

```text
received 9 messages: [100, 101, 102, 200, 201, 202, 300, 301, 302]
total = 1809
```

Nine messages arrived (I sorted them before printing, since the arrival order can vary), and the total is the sum of all nine: 100 + 101 + 102 = 303, 200 + 201 + 202 = 603, 300 + 301 + 302 = 903, and 303 + 603 + 903 = 1809.

There is a detail in that consumer: it holds the lock's guard across an `.await` (a `yield_now`, which gives other tasks a turn). That is allowed with Tokio's async mutex. With the standard library's `std::sync::Mutex`, the same code does not compile:

```rust
let mut g = d.lock().unwrap(); // std MutexGuard
*g += 1;
tokio::task::yield_now().await; // guard still alive across await
```

```text
error: future cannot be sent between threads safely
   --> src/bin/std_guard.rs:7:13
    |
  7 |       let h = tokio::spawn(async move {
    |  _____________^
  8 | |         let mut g = d.lock().unwrap(); // std MutexGuard
  9 | |         *g += 1;
 10 | |         tokio::task::yield_now().await; // guard still alive across await
 11 | |     });
    | |______^ future created by async block is not `Send`
    |
    = help: within `{async block@src/bin/std_guard.rs:7:26: 7:36}`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  --> src/bin/std_guard.rs:10:34
   |
 8 |         let mut g = d.lock().unwrap(); // std MutexGuard
   |             ----- has type `std::sync::MutexGuard<'_, i32>` which is not `Send`
...
10 |         tokio::task::yield_now().await; // guard still alive across await
   |                                  ^^^^^ await occurs here, with `mut g` maybe used later
```

(I cut the last `note:`, which points into the downloaded Tokio source on my machine; it says that `tokio::spawn` requires `Future + Send + 'static`.) This is the `Send` rule from the threads post. A task can be paused at an `.await` and resumed later on a different thread, so everything the task keeps alive across the `.await` must be `Send`. The standard `MutexGuard` is not `Send`, so the compiler rejects the program and points at the `.await` where the guard is still alive. If you never hold the lock across an `.await`, the std mutex is fine and cheaper.

## Do not block the runtime

This is the most important mistake to know about. A task must not do something that blocks the thread (like `std::thread::sleep`, a long CPU loop, or a synchronous file or database call), because while the thread is blocked, no other task that shares it can run. To show it clearly, the demo uses a `current_thread` runtime, where one single thread runs every task. (By default `#[tokio::main]` creates a multi-threaded runtime, according to the Tokio docs; with several threads the effect is softer, but the problem is the same.) A "ticker" task prints a line every 100 ms, while `main` calls `std::thread::sleep` for 500 ms:

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

(These numbers are from the original run.) In the first half, the blocking sleep ends at about 500 ms, and only after that does the first tick appear, at about 600 ms. The ticker could not run at all while the only thread was asleep. Its own 100 ms wait did not even start until `main` reached an `.await` and gave the thread up. In the second half, the same 500 ms sleep is moved into `tokio::task::spawn_blocking`, which runs it on a separate pool of threads meant for blocking work. Now the ticks come on schedule (about 100, 200 and 300 ms) and the blocking result `42` arrives at about 500 ms.

## Compared with Go goroutines

Only facts I am sure of. Go's scheduler is part of its runtime, so `go f()` just works; in Rust, async needs a runtime crate such as Tokio. Async functions are "coloured": an `async fn` can only be awaited from async code, so the choice spreads through your call graph. A Go function can be called from a goroutine or not without any change in its signature.

## Where async breaks

- **Forgetting `.await`** compiles with only a warning, and the work silently never happens. Read the warnings.
- **Cancellation happens at `.await` points.** A future that is dropped stops where it is, so cleanup belongs in `Drop`, not in statements after an await.
- **A std `MutexGuard` held across `.await`** makes the future not `Send`, which `tokio::spawn` rejects. Use Tokio's mutex, or release the lock before the `.await`.
- **Never run blocking code directly in a task.** `thread::sleep`, heavy CPU work, and synchronous file or database drivers should go through `spawn_blocking`.
- **`join!` is concurrency inside one task.** Use `spawn` when you want other threads to help.

## Exercise

1. Write `async fn fetch(id: u32) -> u32` that sleeps 100 ms, then run ten of them with `spawn` and collect the results through their `JoinHandle`s.
2. Wrap one of them in `tokio::time::timeout` of 50 ms and print the error.
3. Run a CPU loop on a `current_thread` runtime beside a ticker, then move it to `spawn_blocking`.

## What's next

The services we can now build need to exchange data. The next post, "Serde and JSON in Rust", covers serializing and deserializing structs, the way we did with `encoding/json` in Go.
