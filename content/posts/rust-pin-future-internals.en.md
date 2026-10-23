+++
date = '2027-02-26T10:00:00+03:30'
draft = false
title = 'Futures, Pin and async internals in Rust'
description = 'Rust async internals: the Future trait, wakers, a hand-written block_on and join, state machine sizes, why Pin exists and cancellation by drop.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "pin", "future", "advanced"]
cover = { image = "/images/covers/rust-pin-future-internals.png", alt = "Futures, Pin and async internals in Rust", hiddenInSingle = true, hiddenInList = true }
+++

The [previous post](/posts/rust-performance-criterion/) was about measuring. This one opens the box under [async/await and Tokio](/posts/rust-async-tokio/): what is a future, who calls it, and why does `Pin` show up in every signature? We will build the pieces ourselves with only the standard library, then run the same code under Tokio at the end.

> Everything was compiled and run with Rust 1.90, edition 2024. Output and compiler messages are copied from those runs.

## The Future trait

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}
```

`poll` returns `Poll::Ready(value)` or `Poll::Pending`. A future does nothing until someone polls it. If it returns `Pending`, it must arrange for the **waker** inside `cx` to be called when progress is possible. Here is a future I wrote by hand: it says `Pending` N times, waking itself each time.

```rust
pub struct CountdownFuture { pub name: &'static str, pub remaining: u32 }

impl Future for CountdownFuture {
    type Output = &'static str;
    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        if self.remaining == 0 {
            Poll::Ready(self.name)
        } else {
            self.remaining -= 1;
            println!("  {}: pending, {} left", self.name, self.remaining);
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}
```

To poll it by hand I need a `Waker`. Implementing `std::task::Wake` for a type inside an `Arc` gives one; here it just counts wake-ups:

```rust
pub struct CountingWaker(pub AtomicUsize);
impl Wake for CountingWaker {
    fn wake(self: Arc<Self>) { self.0.fetch_add(1, Ordering::SeqCst); }
}
// waker = Waker::from(Arc::new(CountingWaker(..))); cx = Context::from_waker(&waker)
// loop { fut.as_mut().poll(&mut cx) } with Pin::new(&mut fut)
```

```text
  countdown: pending, 2 left
poll #1 -> Pending
  countdown: pending, 1 left
poll #2 -> Pending
  countdown: pending, 0 left
poll #3 -> Pending
poll #4 -> Ready("countdown")
wake count = 3
```

If you do not care about wake-ups, `Waker::noop()` is available in Rust 1.90.

## A tiny executor and join

An **executor** is a loop that polls a future and sleeps until the waker fires. Mine parks the thread, and the waker unparks it:

```rust
struct ThreadWaker(Thread);
impl Wake for ThreadWaker {
    fn wake(self: Arc<Self>) { self.0.unpark(); }
}

pub fn block_on<F: Future>(fut: F) -> F::Output {
    let mut fut = std::pin::pin!(fut);
    let waker = Waker::from(Arc::new(ThreadWaker(thread::current())));
    let mut cx = Context::from_waker(&waker);
    loop {
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(v) => return v,
            Poll::Pending => thread::park(),
        }
    }
}
```

`join2(a, b)` is a future that owns two futures and polls both on every `poll`, storing each result until both are done (about 25 lines, it keeps both futures in `Pin<Box<_>>`). Driving two countdowns, A with 3 pending rounds and B with 1:

```text
  A: pending, 2 left
  B: pending, 0 left
  A: pending, 1 left
  A: pending, 0 left
joined = ("A", "B")
```

One thread, two tasks, interleaved. That is all `tokio::join!` is conceptually.

## An async fn is a state machine

The compiler turns an `async` block into an anonymous type implementing `Future`: an enum with one variant per `.await`, holding the locals that live across it. `size_of_val` shows this (debug and release gave the same numbers):

```text
no await        : 1
one await       : 2
8 bytes kept    : 10
1024 bytes kept : 1026
1024 dead early : 2
nested 2x1024   : 1027
```

The future is as large as what must survive an `.await`: a `[u8; 1024]` kept across it costs about 1 KB, but the same array dropped in an inner block before the `.await` costs nothing. The extra 1-2 bytes are the state tag. Treat the exact numbers as a compiler detail of this version; the lesson is that holding big values across awaits makes futures big, and this is why deeply nested async calls sometimes get `Box::pin`ned.

## Why Pin exists

Inside that state machine a local can borrow another local, so the future may contain a pointer into itself. Moving such a value breaks the pointer. A raw-pointer demo (I never dereference the stale pointer):

```text
before move: &value = 0x16b9917f8, stored ptr = 0x16b9917f8, same = true
after move : &value = 0x16b991808, stored ptr = 0x16b9917f8, same = false
```

The field moved, the stored address did not. `Pin<&mut T>` is the promise "this value will not move again" until it is dropped. Most types do not care and implement the auto trait **Unpin**, which makes pinning a no-op: `u32`, `String` and my `CountdownFuture` all pass an `is_unpin` check, so `Pin::new(&mut fut)` works for them. Async blocks are `!Unpin`. Polling one directly fails to compile:

```text
error[E0599]: no method named `poll` found for `async` block ...
help: consider pinning the expression
   let mut pinned = std::pin::pin!(fut);
```

and `Pin::new(&mut fut)` gives ``the trait `Unpin` is not implemented for `{async block ...}` ``, with a note suggesting `pin!` or `Box::pin`. Two ways to pin: `Box::pin(fut)` puts it on the heap (see [smart pointers](/posts/rust-smart-pointers/)), and `std::pin::pin!(fut)` pins it on the stack. Both poll fine:

```text
Box::pin   -> Ready(1)
pin!       -> Ready(1)
```

## Cancellation is dropping

A future is just a value, so dropping it cancels it. A guard created inside an async block is destroyed when the future is dropped, even though the block never finished:

```text
  slow: pending, 4 left
polled once, now dropping the future
  drop guard inside async
after scope
```

"never printed" never printed. This is the same `Drop` guard idea as in Tokio's `select!`: cleanup belongs in `Drop`.

## Same code under Tokio

My `CountdownFuture` runs unchanged under `tokio::runtime::Builder::new_current_thread().build()?.block_on(...)`, with identical output to my executor (`start`, two pendings, `got a`, `result = 42`). Tokio adds timers, IO and multi-thread scheduling, but the contract is the same `poll` and `Waker`.

## A few things to watch

- Returning `Pending` without arranging a wake-up means the task sleeps forever.
- Never poll a future again after `Ready`; `async` blocks panic with "resumed after completion".
- Large locals across `.await` bloat futures.
- Moving a pinned `!Unpin` value is impossible in safe code; do not use `unsafe` to work around it.

## Exercise

Write `yield_now()`: a future that returns `Pending` once (calling `wake_by_ref`) and `Ready(())` the second time. Run two async blocks that loop with it under `join2`.

## What's next

Next is observability in Rust with `tracing`: structured logs and spans for async code.
