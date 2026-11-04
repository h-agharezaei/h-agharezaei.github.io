+++
date = '2027-01-07T10:00:00+03:30'
draft = false
title = 'Concurrency with threads in Rust'
description = 'Rust threads with std only: spawn and join, move closures, mpsc channels, Arc and Mutex, Send and Sync, scoped threads, and data races as compile errors.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "concurrency", "threads", "intermediate"]
cover = { image = "/images/covers/rust-concurrency-threads.png", alt = "Concurrency with threads in Rust", hiddenInSingle = true }
+++

Imagine two threads that each add one to the same counter. "Add one" sounds like a single step, but the machine does three: read the current value, add one to it, write the result back. If both threads read the value `5` before either one writes, both write `6`, and one of the two increments is lost. The program does not crash and prints no error; the number is just wrong, and wrong differently from run to run. This bug is called a {{< term "data-race" "data race" >}}: two threads touching the same memory at the same time, at least one of them writing, with nothing coordinating them. It is one of the hardest bugs to find, because the code looks correct.

Rust's answer is to refuse to compile such a program. The rules you already know, ownership and borrowing, turn out to be exactly what is needed, and Rust calls the result "fearless concurrency". This post builds it up step by step: starting a thread, giving it data, passing messages, sharing state with a lock, and the two small traits (`Send` and `Sync`) that make the compiler's refusals possible. We use only the standard library, and every compiler error below comes from a real compile. It follows the tests and docs of the [previous post](/posts/rust-testing-docs/). If you know Go, this is the counterpart of [goroutines and channels](/posts/go-goroutines-channels/) and [sync, select and context](/posts/go-sync-select-context/).

> Everything here ran on Rust 1.90 (the same version as the original run). Programs that print from several threads can print in a different order on each run; where that matters I say so. A few small programs (a `move` of a number, and two threads changing one counter) were not in the original demo; I wrote them for this post and ran them separately. I removed the "For more information..." lines, some `note:` lines, and the pointers into the standard library source from the error messages.

## Starting a thread: spawn, join and panics

A {{< term "os-thread" "thread" >}} is an independent line of execution inside your program. `thread::spawn` starts a new operating-system thread that runs a closure (the [closures post](/posts/rust-closures-iterators/) explains them) at the same time as the rest of your code, and returns a **`JoinHandle`**. Calling `join()` on it waits for the thread to finish and returns a `Result`: `Ok` with the closure's return value, or `Err` if the thread panicked. The demo starts one thread that works and one that panics on purpose:

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

The first thread returns the sum of 1 to 10, and `join` hands us `55`. The second thread panics, and Rust prints the panic message (to stderr, so in a terminal it can appear in a different place relative to the other lines). Then `join` returns an `Err`, and our `match` prints the last line: a panic in a worker does not kill the program. You decide what to do with the `Err`. (I removed the `RUST_BACKTRACE` note line.)

## Why the closure needs `move`

A thread can keep running after the function that created it has returned. So what happens if the thread's closure borrows a local variable?

```rust
let v = vec![1, 2, 3];
let h = thread::spawn(|| println!("{v:?}"));
h.join().unwrap();
```

```text
error[E0373]: closure may outlive the current function, but it borrows `v`, which is owned by the current function
 --> src/bin/no_move.rs:5:27
  |
5 |     let h = thread::spawn(|| println!("{v:?}"));
  |                           ^^            - `v` is borrowed here
  |                           |
  |                           may outlive borrowed value `v`
  |
note: function requires argument type to outlive `'static`
help: to force the closure to take ownership of `v` (and any other referenced variables), use the `move` keyword
  |
5 |     let h = thread::spawn(move || println!("{v:?}"));
  |                           ++++
```

This is the dangling reference from the [lifetimes post](/posts/rust-lifetimes/) again. The compiler cannot know that we `join` right away, and `v` would be dropped when `main` ends while the thread might still be reading it. The note says what `spawn` demands: the closure must not borrow anything that could go away (`'static`). The help gives the fix: write `move`, so the thread owns `v`. Then the program compiles and prints `[1, 2, 3]`.

One surprise about `move`: it moves, but for simple types such as numbers "moving" means copying. If we move a counter into a thread and increase it there:

```rust
let mut counter = 0;
let h = thread::spawn(move || {
    counter += 1;
    println!("thread sees {counter}");
});
h.join().unwrap();
println!("main sees {counter}");
```

```text
thread sees 1
main sees 0
```

The thread changed its own copy and `main` still sees `0`. This is not a bug in Rust, but it shows that `move` does not give you a shared counter. For that we need the tools in the next sections.

## Channels: sending values between threads

The simplest safe way for threads to cooperate is to not share anything: one thread sends a value, another receives it. `std::sync::mpsc` ("multiple producer, single consumer") gives you a {{< term "mpsc-channel" "channel" >}}: you get a sender (`tx`) and a receiver (`rx`), and you clone the sender for each producing thread.

In this demo three threads each send two messages, and the main thread collects them all:

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

Note the line `drop(tx)`. The receiver's loop (`rx.iter()`) ends only when every sender has been dropped. The three clones go away when their threads finish, but the original `tx` still lives in `main`, so we drop it by hand. Forget this line and the loop waits forever. I sorted the messages before printing because the order in which the threads deliver them is not fixed; without the sort, the lines can come in a different order on each run.

Sending a value moves it, so the sender cannot use it afterwards:

```rust
let s = String::from("hello");
tx.send(s).unwrap();
println!("{s}");
```

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/use_after_send.rs:9:20
  |
7 |         let s = String::from("hello");
  |             - move occurs because `s` has type `String`, which does not implement the `Copy` trait
8 |         tx.send(s).unwrap();
  |                 - value moved here
9 |         println!("{s}");
  |                    ^ value borrowed here after move
```

This is the same ownership rule as always: after `send(s)` the string belongs to the receiver. If the sender could keep using it, two threads might touch the same string, which is exactly what we want to avoid. So "share memory by communicating" is enforced here by the compiler, not by discipline.

## Shared state: why a lock, and Arc plus Mutex

Sometimes threads really must share one piece of data, like our counter. Can we just let two threads change it? Let's see what the compiler says (this version uses `thread::scope`, which I explain below, so the closures may borrow):

```rust
let mut counter = 0;
thread::scope(|s| {
    s.spawn(|| counter += 1);
    s.spawn(|| counter += 1);
});
```

```text
error[E0499]: cannot borrow `counter` as mutable more than once at a time
 --> src/bin/x_two_mut.rs:7:17
  |
5 |     thread::scope(|s| {
  |                    - has type `&'1 Scope<'1, '_>`
6 |         s.spawn(|| counter += 1);
  |         ------------------------
  |         |       |  |
  |         |       |  first borrow occurs due to use of `counter` in closure
  |         |       first mutable borrow occurs here
  |         argument requires that `counter` is borrowed for `'1`
7 |         s.spawn(|| counter += 1);
  |                 ^^ ------- second borrow occurs due to use of `counter` in closure
  |                 |
  |                 second mutable borrow occurs here
```

This is the borrowing rule you know ("one mutable reference at a time") applied to threads. Each closure wants a mutable borrow of `counter`, and the compiler says no to the second one. The data race from the opening cannot even be written. This is the heart of the idea: the data race is just "two mutable accesses at once", which the borrow checker already forbids.

So how do we share a counter on purpose? With a type whose job is to make the access safe: a **`Mutex`** (mutual exclusion lock). A thread calls `lock()` to get exclusive access, and the lock is released automatically when the returned guard goes out of scope. In Rust the data lives inside the mutex, so you cannot reach it without locking. A `Mutex` must also be shared by several threads, and each thread needs to own a handle to it. For that we use {{< term "arc" "Arc" >}}, an "atomically reference counted" pointer: the thread-safe version of `Rc` from the [smart pointers post](/posts/rust-smart-pointers/). Together, `Arc<Mutex<T>>` is shared, lockable data:

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

Eight threads each add one a thousand times, and the result is exactly 8000. Each thread gets its own `Arc` clone (a new handle to the same counter), `lock()` gives it exclusive access for one increment, and the guard is dropped at the end of that statement, which unlocks the mutex. `lock()` returns a `Result`, which is why there is an `unwrap()`; the section on poisoning below explains when it can be an `Err`.

## Send and Sync: why the compiler can tell

How does the compiler know that `Arc<Mutex<i32>>` is fine to use in a thread but something else is not? Try `Rc` instead of `Arc`:

```rust
let counter = Rc::new(Mutex::new(0));
let c = Rc::clone(&counter);
let h = thread::spawn(move || {
    *c.lock().unwrap() += 1;
});
```

```text
error[E0277]: `Rc<std::sync::Mutex<i32>>` cannot be sent between threads safely
   --> src/bin/rc_mutex.rs:8:27
    |
  8 |       let h = thread::spawn(move || {
    |               ------------- ^------
    |               |             |
    |  _____________|_____________within this `{closure@src/bin/rc_mutex.rs:8:27: 8:34}`
    | |             |
    | |             required by a bound introduced by this call
  9 | |         *c.lock().unwrap() += 1;
 10 | |     });
    | |_____^ `Rc<std::sync::Mutex<i32>>` cannot be sent between threads safely
    |
    = help: within `{closure@src/bin/rc_mutex.rs:8:27: 8:34}`, the trait `Send` is not implemented for `Rc<std::sync::Mutex<i32>>`
note: required by a bound in `spawn`
    |
726 |     F: Send + 'static,
    |        ^^^^ required by this bound in `spawn`
```

Read it from the bottom. The signature of `spawn` says `F: Send + 'static`: the closure it receives must be {{< term "send-and-sync" "Send" >}}. The closure contains an `Rc`, and `Rc` is not `Send`, so the closure is not either. The message points at exactly that.

`Send` and `Sync` are two **marker traits**, traits with no methods that only label a type. A type is `Send` if it is safe to move it to another thread. A type is `Sync` if it is safe for several threads to hold a shared reference (`&T`) to it at once. `Rc` updates its reference counter without any protection, so two threads cloning it could corrupt the count. It is therefore neither `Send` nor `Sync`. `Arc` uses atomic operations for the counter, so it is both (when the data inside is).

You never write `Send` or `Sync` yourself: the compiler works them out from the fields of a type. A struct is `Send` if all its fields are. That is the whole mechanism, and it is worth stating plainly: a data race needs shared data that is changed without coordination. Ownership forbids the sharing, the borrow rules forbid the unsynchronized change, and `Send`/`Sync` stop you from sneaking in a type that is unsafe across threads. (Code inside `unsafe` blocks can still break the rules, but safe code cannot.)

## RwLock, atomics and scoped threads

Three more tools from the standard library. `RwLock` is a lock that allows many readers at once or one writer. An atomic type, such as `AtomicUsize`, does a single operation like "add one" indivisibly and needs no lock at all, which is the right tool for a simple counter. The demo starts four threads that each read a shared config and add one to a shared counter, and afterwards the main thread writes a new config:

```rust
let config = Arc::new(RwLock::new(String::from("v1")));
let hits = Arc::new(AtomicUsize::new(0));
// 4 threads: config.read().unwrap(); hits.fetch_add(1, Ordering::Relaxed);
// afterwards: *config.write().unwrap() = String::from("v2");
```

```text
hits = 4, config = v2
```

(The full program with the spawning loop is in the local demo.) Four hits were counted, and the write changed the config to `v2`. The `Ordering` argument says how strictly the CPU must order memory operations around the atomic; `SeqCst` is the safest choice when you are unsure, and the demo uses `Relaxed` for the increments, which is enough for a plain counter.

The last tool solves the `move` and `Arc` hassle for a common case. `thread::scope` guarantees that every thread started inside it has finished before it returns, so those threads may borrow local data directly, without `move` or `Arc`:

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

The vector is split in two halves, each half is summed in its own thread, and afterwards `data` is still ours to use. Both threads only read, so sharing is fine. (In the failing example above, both wanted to write, which is why that one did not compile.) The same idea works for chunked work: I split a vector of 1,000,000 numbers into 4 chunks, summed each in a scoped thread, and compared with the single-threaded sum. The program printed `single = 500000500000, parallel = 500000500000, equal = true`. I did not measure speed, so I claim nothing about it.

## Mutex poisoning

What if a thread panics while it holds a lock? The data may be half-updated. Rust marks the mutex as **poisoned** as a warning. The demo makes a thread lock the mutex and panic, then asks about the state:

```text
thread '<unnamed>' panicked at src/bin/poison.rs:9:9:
died while holding the lock
thread result is_err = true
is_poisoned = true
lock failed, but data is recoverable: 0
```

The first two lines are the panic message from the thread. Then: the thread's result was an `Err` (it panicked), the mutex reports `is_poisoned = true`, and so `lock()` returns an `Err` too. That error is not a dead end: `into_inner()` on it still gives you the guard, so if you decide the data is fine, you can keep using it. Here it prints `0`, the value that was in there.

## What Rust does not prevent

- **Forgetting `drop(tx)`** makes the receiving loop wait forever, since the channel never closes.
- **Holding a `MutexGuard` for a long time** makes your threads wait in line. Keep the locked section short.
- **Deadlocks and logic races are still possible.** Rust prevents data races, not deadlocks. Locking two mutexes in opposite orders in two threads can still hang. A "logic race" (a wrong result because of the order of operations, with each single access being safe) is also possible.
- **`unwrap()` on `lock()`** is fine in examples. In real code decide what a poisoned lock should mean for your program.
- **Compared with Go:** both are good at concurrency. Rust rejects data races at compile time. Go finds them at run time with the `-race` flag, and only on code paths that actually execute.

## Exercise

1. Rewrite the counter with `AtomicUsize` instead of `Mutex`.
2. Make a pool of 3 workers that receive numbers over a channel and send back their squares on a second channel. (Hint: with `mpsc` there is one receiver, so you need to decide how to share it.)

## What's next

A thread is an operating-system resource and is heavy when you have thousands of tasks that mostly wait for the network or disk. That is the problem the next post, "async/await and Tokio in Rust", solves.
