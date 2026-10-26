+++
date = '2027-01-07T10:00:00+03:30'
draft = false
title = 'Concurrency with threads in Rust'
description = 'Rust threads with std only: spawn and join, move closures, mpsc channels, Arc and Mutex, Send and Sync, scoped threads, and data races as compile errors.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "concurrency", "threads", "intermediate"]
cover = { image = "/images/covers/rust-concurrency-threads.png", alt = "Concurrency with threads in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-testing-docs/) we covered tests and documentation. Now to the feature Rust is most proud of: "fearless concurrency". The claim is that ownership and borrowing, which you already know, also rule out data races at compile time. We will use only the standard library, and every error below comes from a real compile. If you know Go, this is the counterpart of [goroutines and channels](/posts/go-goroutines-channels/) and [sync, select and context](/posts/go-sync-select-context/).

> Everything here ran on Rust 1.90.

## spawn, join and panics

`thread::spawn` starts an OS thread and returns a **JoinHandle**. Calling `join()` waits for the thread and returns a `Result`: `Ok` with the return value, or `Err` if the thread panicked.

```rust
let h = thread::spawn(|| (1..=10).sum::<u32>());
println!("sum = {}", h.join().unwrap());

let bad = thread::spawn(|| { if true { panic!("worker failed"); } 5 });
match bad.join() {
    Ok(v) => println!("ok {v}"),
    Err(_) => println!("worker panicked, main is still alive"),
}
```

```text
sum = 55
thread '<unnamed>' panicked at src/bin/spawn_join.rs:9:13:
worker failed
worker panicked, main is still alive
```

A panic in a worker does not kill the program. You decide what to do with the `Err`.

## Why closures need move

A spawned thread may outlive the function that created it, so it cannot borrow local variables:

```text
error[E0373]: closure may outlive the current function, but it borrows `v`, which is owned by the current function
5 |     let h = thread::spawn(|| println!("{v:?}"));
  |                           ^^            - `v` is borrowed here
  |                           |
  |                           may outlive borrowed value `v`
help: to force the closure to take ownership of `v` (and any other referenced variables), use the `move` keyword
```

Writing `move ||` hands ownership of `v` to the thread, and then it compiles and prints `[1, 2, 3]`.

## Channels: moving ownership between threads

`std::sync::mpsc` means multiple producer, single consumer. Clone the sender for each producer. Note the `drop(tx)`: the receiver iterates until all senders are gone, including the original.

```rust
let (tx, rx) = mpsc::channel();
for id in 0..3 {
    let tx = tx.clone();
    thread::spawn(move || {
        for n in 0..2 {
            tx.send(format!("producer {id} item {n}")).unwrap();
        }
    });
}
drop(tx);
let mut all: Vec<String> = rx.iter().collect();
all.sort();
```

```text
producer 0 item 0
producer 0 item 1
producer 1 item 0
producer 1 item 1
producer 2 item 0
producer 2 item 1
```

I sorted the messages because arrival order between threads is not fixed. Sending a value moves it, so the sender cannot touch it afterwards:

```text
error[E0382]: borrow of moved value: `s`
8 |         tx.send(s).unwrap();
  |                 - value moved here
9 |         println!("{s}");
  |                    ^ value borrowed here after move
```

This is "share memory by communicating" enforced by the compiler.

## Shared state: Arc and Mutex

When threads must share data, use `Arc<Mutex<T>>`. **Arc** is an atomically reference-counted pointer, the thread-safe version of `Rc`. **Mutex** gives exclusive access through `lock()`.

```rust
let counter = Arc::new(Mutex::new(0));
let mut handles = Vec::new();
for _ in 0..8 {
    let counter = Arc::clone(&counter);
    handles.push(thread::spawn(move || {
        for _ in 0..1000 { *counter.lock().unwrap() += 1; }
    }));
}
for h in handles { h.join().unwrap(); }
println!("final = {}", *counter.lock().unwrap());
```

```text
final = 8000
```

Eight threads, a thousand increments each, and the result is exactly 8000. The lock is released when the guard goes out of scope.

## Send and Sync: how data races become compile errors

What if we use `Rc` instead of `Arc`?

```text
error[E0277]: `Rc<std::sync::Mutex<i32>>` cannot be sent between threads safely
  |
  = help: within `{closure@src/bin/rc_mutex.rs:8:27: 8:34}`, the trait `Send` is not implemented for `Rc<std::sync::Mutex<i32>>`
note: required by a bound in `spawn`
726 |     F: Send + 'static,
```

Two marker traits explain this. A type is **Send** if it is safe to move to another thread. A type is **Sync** if it is safe to share by reference between threads (`&T` is Send). `Rc` counts references without atomics, so it is neither. `spawn` requires `Send`, and the compiler derives it automatically from the fields. That is the whole mechanism: a data race needs unsynchronized shared mutation, and the type system refuses to let you write it. More on `Rc` in [smart pointers](/posts/rust-smart-pointers/).

## RwLock, atomics and scoped threads

`RwLock` allows many readers or one writer. For a simple counter, `AtomicUsize` avoids a lock entirely:

```rust
let config = Arc::new(RwLock::new(String::from("v1")));
let hits = Arc::new(AtomicUsize::new(0));
// 4 threads: config.read().unwrap(); hits.fetch_add(1, Ordering::Relaxed);
// afterwards: *config.write().unwrap() = String::from("v2");
```

```text
hits = 4, config = v2
```

(The full program with the spawning loop is in my local demo.) The `Ordering` argument controls memory ordering; `SeqCst` is the safe default when unsure.

`thread::scope` guarantees its threads finish before it returns, so they may borrow local data without `move` or `Arc`:

```rust
let data = vec![1, 2, 3, 4, 5, 6];
let (left, right) = data.split_at(3);
let (a, b) = thread::scope(|s| {
    let h1 = s.spawn(|| left.iter().sum::<i32>());
    let h2 = s.spawn(|| right.iter().sum::<i32>());
    (h1.join().unwrap(), h2.join().unwrap())
});
```

```text
left = 6, right = 15, data still ours: 6
```

The same idea works for chunked work: I split a vector of 1,000,000 numbers into 4 chunks, summed each in a scoped thread, and compared with the single-threaded sum. Both gave 500000500000. I did not measure speed, so I claim nothing about it.

## Mutex poisoning

If a thread panics while holding a lock, the mutex is marked **poisoned**, a warning that the data may be half-updated:

```text
thread result is_err = true
is_poisoned = true
lock failed, but data is recoverable: 0
```

`lock()` returns `Err`, and `into_inner()` on that error still gives you the guard if you decide the data is fine.

## A few things to watch

- Forgetting `drop(tx)` makes the receiving loop wait forever.
- Holding a `MutexGuard` for long serializes your threads; keep critical sections short.
- Rust prevents data races, not deadlocks or logic races. Locking two mutexes in opposite orders still hangs.
- `unwrap()` on `lock()` is fine in examples, but decide deliberately what a poisoned lock means in real code.
- Compared with Go: both are good at concurrency. Rust rejects data races at compile time; Go finds them at run time with the `-race` flag, and only on code paths that actually execute.

## Exercise

1. Rewrite the counter with `AtomicUsize` instead of `Mutex`.
2. Make a pool of 3 workers that receive numbers over a channel and send back their squares on a second channel.

## What's next

Threads are heavy when you have thousands of concurrent tasks, mostly waiting on I/O. Next: async/await and Tokio in Rust.
