+++
date = '2027-02-26T10:00:00+03:30'
draft = false
title = 'Futures, Pin and async internals in Rust'
description = 'Rust async internals: the Future trait, wakers, a hand-written block_on and join, state machine sizes, why Pin exists and cancellation by drop.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "pin", "future", "advanced"]
cover = { image = "/images/covers/rust-pin-future-internals.png", alt = "Futures, Pin and async internals in Rust", hiddenInSingle = true }
+++

In [the async and Tokio post](/posts/rust-async-tokio/) we saw that calling an `async fn` does not run its body; it only returns a {{< term "rust-future" "future" >}}, which does nothing until somebody waits for it. There we only said that behind the scenes the runtime asks the future "are you done?" with a method called `poll`, and we promised to look at it more closely later. This post is that later. We have two questions. The first: what exactly does "somebody waits for it" mean? What starts a future, and what finds out that it has finished? The second: why does a {{< term "rust-pin" "Pin" >}} appear in the signature wherever we deal with futures, and why does it look so scary?

This post answers both by building the things ourselves, after [measuring with Criterion](/posts/rust-performance-criterion/). We build a simple future by hand, write a small {{< term "rust-executor" "executor" >}} that runs it, look at what an `async fn` is on the inside, and then understand with a simple picture why `Pin` is needed. All the pieces are built with only the standard library, and at the end we run the same code under Tokio.

> I recompiled and re-ran all the code below with Rust 1.90 (`rustc 1.90.0`) and edition 2024. The programs use only the standard library, except the last comparison, which has `tokio` 1.54.1 (feature `rt`, from `Cargo.lock`). The outputs and compiler messages are copied from those runs. A few small examples (an async fn with a reference to its own local, `swap` on a pinned future, moving a `Pin<Box<_>>`, and polling after completion) I wrote and ran as separate programs, only to show them here. Memory addresses differ from run to run. From the error messages I removed the `note:` lines and the "For more information…" lines.

## The Future trait

Let us start from the contract itself. This is everything a future must have:

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}
```

It has one method: `poll`. Whoever runs the future says to it "move forward, are you finished?". A future can give two answers: `Poll::Ready(value)` means "done, and here is the result", and `Poll::Pending` means "not yet".

Think of a child in a car who keeps asking "are we there yet?". If the child asks every second, everyone gets tired. So Rust has a convention: if a future says `Pending`, it must arrange to tell the runner when progress is possible. The tool for this notification is the {{< term "rust-waker" "waker" >}}, which lives inside `cx` (of type `Context`). A waker is like a bell that the future can ring, and whoever runs the future (the executor) does not come back to it until that bell rings.

Two other pieces I explain later: why `Pin<&mut Self>` appears instead of a plain `&mut self` (in the section "Why Pin exists"), and `Context<'_>`, which is just the box that holds the waker.

### A hand-written future

Three questions in a row: how many times should it say `Pending`? What should it print? When should it ring the waker? I wrote this future so that it says `Pending` N times and wakes itself up each time:

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

Each time `poll` is called: if `remaining` is zero, it announces the result as ready (the future's name). Otherwise it subtracts one from `remaining`, prints a line, calls `wake_by_ref()`, that is, "ring the bell, come back to me", and returns `Pending`.

To poll by hand we need a `Waker`. If a type implements `std::task::Wake` and lives inside an `Arc`, we can make a waker from it. This one only counts how many times the bell rang:

```rust
pub struct CountingWaker(pub AtomicUsize);
impl Wake for CountingWaker {
    fn wake(self: Arc<Self>) { self.0.fetch_add(1, Ordering::SeqCst); }
}
// waker = Waker::from(Arc::new(CountingWaker(..))); cx = Context::from_waker(&waker)
// loop { fut.as_mut().poll(&mut cx) } with Pin::new(&mut fut)
```

The `manual_poll` program makes a `CountdownFuture` with a count of 3 and polls it in a loop until `Ready`. The output:

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

The first three polls gave `Pending`; each printed a line from inside the future and rang the waker. The fourth poll saw that `remaining` was zero and returned `Ready("countdown")`. `wake count = 3` means the waker rang three times, exactly the number of `Pending`s. (In this manual example `Pin::new(&mut fut)` works because `CountdownFuture` is `Unpin`. The meaning comes in the Pin section.)

If you do not care about wake-ups, `Waker::noop()` is available in Rust 1.90: a waker that does nothing. The same program, with it, prints two more lines: `noop: Pending` and then `noop: Ready("noop")` (plus the future's own `noop: pending, 0 left` line before the first).

## A small executor

So who polls the future, and who answers the waker's bell? The **executor**. The simplest one is a loop that polls the future, goes to sleep if it was `Pending`, and wakes up when the waker rings, to poll again. Mine parks the thread (puts it to sleep) and the waker unparks it:

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

Line by line: `pin!` holds the future in a fixed place (see the Pin section). The waker is built from the current thread. In the loop, `poll` is called; `Ready` means done, so return the result; `Pending` means `thread::park()`, sleep until the waker rings. Because `CountdownFuture` wakes itself before returning `Pending`, the thread wakes immediately and continues. The `exec` program runs an async block with this executor:

```text
start
  a: pending, 1 left
  a: pending, 0 left
got a
result = 42
```

The async block first prints `start` and then `.await`s a `CountdownFuture`. Two `Pending`s (the two `pending` lines), then `Ready`, `got a` was printed, and the block returned `42`, which `block_on` handed to us.

### join: two jobs on one thread

With the same pieces we can write a `join2`: a future that holds two futures, polls both on every `poll`, and keeps the result of each until both are finished (about 25 lines; it keeps both futures in `Pin<Box<_>>`). I ran two countdowns, A with 3 rounds of pending and B with 1:

```text
  A: pending, 2 left
  B: pending, 0 left
  A: pending, 1 left
  A: pending, 0 left
joined = ("A", "B")
```

One thread, two jobs interleaved: the first poll advanced both (the first line is A and the second is B), B became `Ready` on the next round, and A needed two more rounds. When both were done, `join2` returned the results as a tuple. `tokio::join!` is conceptually the same.

## An async fn is a state machine

Now, what does the compiler turn our `async fn` into? An `async` block has points (every `.await`) where the work may stop and continue later. So the future must remember "where was I and which variables did I have". For each async block the compiler builds an unnamed type that implements `Future`: an enum (a **state machine**) with one state per `.await`, holding the local variables that are alive across that pause.

We can measure this. `size_of_val` gives the size of the future itself in bytes (debug and release gave the same numbers):

```text
no await        : 1
one await       : 2
8 bytes kept    : 10
1024 bytes kept : 1026
1024 dead early : 2
nested 2x1024   : 1027
```

Line by line: an async fn with no await is just 1 byte (the state tag). With one await, 2 bytes. When an 8-byte array crosses an `.await`, it becomes 10 bytes, and for 1024 bytes, 1026. But the same 1024-byte array, if it is destroyed in an inner block before the `.await`, leaves the future at only 2 bytes (`1024 dead early`), because it is no longer alive at the pause. And two nested calls that each hold 1 kilobyte came to 1027 bytes, not about 2000. The reason is probably that the first inner future is discarded when it finishes and the second inner future can use the same space; I did not check the layout details.

So the size of a future equals what has to cross an `.await`. The exact numbers are compiler details of this version; the lesson is that holding large values across an await makes the future large, and that is why nested async calls are sometimes wrapped in `Box::pin`.

## Why Pin exists

Now the second question. Look at what this async fn does:

```rust
async fn uses_own_local() -> usize {
    let buf = [7u8; 16];
    let r = &buf; // points at a local of this very future
    ready(()).await; // `buf` and `r` must both survive the pause
    r.len()
}
```

`r` is a reference to `buf`, and both cross an `.await`. So both must be stored inside the future, which means one field of the future points to another field of itself. (This code compiles, and with our own `block_on` it printed `result = 16`; the future was 32 bytes.) Such a structure is called **self-referential**. A picture:

```text
before the move:                     after the move:
+----------------------+             +----------------------+
| value = 7            | <--+        | value = 7            |   (new place)
| ptr   = &value       | ---+        | ptr   = old address  | ---> where value no longer is
+----------------------+             +----------------------+
```

Where is the problem? Moving means copying the bytes to a new place. `value` went to the new place, but `ptr` kept the old address. This is a dangling pointer. It is easy to show with a plain struct holding a raw pointer (I never dereference the old pointer; reading through it is undefined behaviour):

```text
before move: &value = 0x16d969488, stored ptr = 0x16d969488, same = true
after move : &value = 0x16d969498, stored ptr = 0x16d969488, same = false
```

(The addresses change from run to run.) Before the move the address of `value` and the stored address were the same (`same = true`). After the move `value` is at a new address but `ptr` still has the old one (`same = false`). For a future that might be moved between two `poll`s this is a disaster, because `r` in `r.len()` would read from the old address.

Rust's solution is to promise that a future is not moved after its first `poll`. `Pin<&mut T>` is exactly that promise: "this value will not move until it is dropped". That is why `poll` takes `self: Pin<&mut Self>` instead of `&mut self`.

### Unpin: most types do not care

Most types have no pointers to themselves, and moving them causes no problem. These types automatically get a trait called **Unpin**, which means "pinning me changes nothing". For them `Pin::new(&mut x)` works. `u32`, `String` and my `CountdownFuture` all passed a simple `is_unpin` check. But async blocks may be self-referential, so they are `!Unpin`. If you try to poll one directly:

```text
error[E0599]: no method named `poll` found for `async` block `{async block@src/bin/nopin.rs:6:19: 6:24}` in the current scope
  --> src/bin/nopin.rs:11:17
   |
11 |     let _ = fut.poll(&mut cx);
   |                 ^^^^ method not found in `{async block@src/bin/nopin.rs:6:19: 6:24}`
   |
help: consider pinning the expression
   |
11 ~     let mut pinned = std::pin::pin!(fut);
12 ~     let _ = pinned.as_mut().poll(&mut cx);
```

The compiler says there is no `poll` method on `fut` itself: `poll` is defined only on `Pin<&mut Self>`. The `help` part shows the way too: pin it with `pin!`. The shortcut `Pin::new(&mut fut)` does not work either:

```text
error[E0277]: `{async block@src/bin/nopin_new.rs:7:19: 7:24}` cannot be unpinned
    --> src/bin/nopin_new.rs:12:22
     |
  12 |     let _ = Pin::new(&mut fut).poll(&mut cx);
     |             -------- ^^^^^^^^ the trait `Unpin` is not implemented for `{async block@src/bin/nopin_new.rs:7:19: 7:24}`
     |             |
     |             required by a bound introduced by this call
     |
             consider using `Box::pin` if you need to access the pinned value outside of the current scope
```

`Pin::new` is only for `Unpin` types, because only those can be pinned without risk, and an async block is not one of them. The message suggests another way too: `Box::pin`.

### Two ways to pin

`Box::pin(fut)` puts the future on the heap (see [smart pointers](/posts/rust-smart-pointers/)): even if the `Box` itself moves, what is inside the heap stays where it is. `std::pin::pin!(fut)` pins it on the stack, and you can no longer touch the variable itself. Both are polled correctly:

```text
Box::pin   -> Ready(1)
pin!       -> Ready(1)
```

To see that a `Box` really does not move the future, in a separate program I printed the future's address before and after moving the `Pin<Box<_>>`, and `future stayed at the same address: true` came out: only the pointer moved.

And why can safe code not move a pinned future? Because getting a `&mut T` from a `Pin<&mut T>` needs `DerefMut`, which is implemented only for `Unpin`. I tried it with two pinned futures and `std::mem::swap`:

```text
error[E0596]: cannot borrow data in dereference of `Pin<&mut impl Future<Output = ()>>` as mutable
  --> src/bin/x_swap.rs:11:20
   |
11 |     std::mem::swap(&mut *a, &mut *b);
   |                    ^^^^^^^ cannot borrow as mutable
   |
   = help: trait `DerefMut` is required to modify through a dereference, but it is not implemented for `Pin<&mut impl Future<Output = ()>>`
```

The compiler does not let you take a `&mut` to a pinned future, so you cannot move it with `swap` or `mem::replace`. This is what prevents the dangling pointer.

## Cancellation means drop

A future is just a value, so dropping it cancels it ({{< term "task-cancellation" "cancellation by drop" >}}). In the `cancel` program there is an async block that creates a `Guard` (with a `Drop` implementation that prints something) and then `.await`s a countdown of 5. I poll it only once and then drop the future:

```text
  slow: pending, 4 left
polled once, now dropping the future
  drop guard inside async
after scope
```

The first poll got as far as the first `Pending` (the first line). Then the future was dropped, and the guard that was alive inside it was destroyed too (`drop guard inside async`), even though the block never finished. The line `never printed`, which came after the await, was never printed. This is the idea behind `select!` and `timeout` in Tokio: the work that did not win is dropped, so cleanup belongs in `Drop`, not in the lines after `.await`.

## The same code under Tokio

I ran my `CountdownFuture` unchanged under `tokio::runtime::Builder::new_current_thread().build()?.block_on(...)`, and the output was the same as with my own executor (`start`, two `pending` lines, `got a` and `result = 42`). Tokio adds timers, I/O and multi-threaded scheduling, but the contract is the same `poll` and `Waker`.

## Rules of the Future contract

- **Returning `Pending` without arranging a wake-up** makes the future forgotten forever, because the executor waits for the bell. (According to the `Future` documentation, after `Pending` the task is polled again only when the waker has been woken.) I did not run this.
- **Do not poll a future again after `Ready`.** For an async block this is a panic. I tried it: the first time `Ready(5)` came out, and the second time `` `async fn` resumed after completion ``.
- **Large local variables across `.await`** make the future large (see the size table above).
- **Moving a pinned `!Unpin` value is not possible in safe code**; do not reach for `unsafe` to get around it.

## Exercise

Write `yield_now()`: a future that returns `Pending` the first time (with `wake_by_ref`) and `Ready(())` the second time. Run two async blocks that loop using it under `join2`.

## What's next

"Observability in Rust with tracing": structured logs and spans to see the story of a request among interleaved tasks.
