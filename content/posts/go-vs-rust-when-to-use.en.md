+++
date = '2026-12-26T10:00:00+03:30'
draft = false
title = 'Go or Rust? When to use which'
description = 'An honest Go vs Rust comparison from a backend engineer: one measured microbenchmark, a table of real differences, and a guide for when each language fits.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "comparison", "backend"]
cover = { image = "/images/covers/go-vs-rust-when-to-use.png", alt = "Go or Rust? When to use which", hiddenInSingle = true, hiddenInList = true }
+++

The Go fundamentals are done and the Rust series has reached ownership, borrowing and errors, so this is a good place to stop and ask the question people always ask: which one should I use? I work mainly in Go and Node.js and I am still learning Rust, so treat this as one person's view with a little data, not a verdict. I will mark clearly what I measured and what is only my experience.

## One small measurement

The task: count word frequencies in a generated text of 10 million words (about 99,500 distinct words), written the obvious way in each language. The text is generated in memory by the same tiny LCG in both programs and is not part of the timing. The core of each program:

```go
counts := make(map[string]int)
for w := range strings.FieldsSeq(text) {
	counts[w]++
}
```

```rust
let mut counts: HashMap<&str, usize> = HashMap::new();
for w in text.split_whitespace() {
    *counts.entry(w).or_insert(0) += 1;
}
```

Both print the same result, which is how I know they do the same work:

```text
distinct=99501 top=w2709:259
```

Everything below was measured on one arm64 macOS laptop with Go 1.26 and Rust 1.90 (`cargo build --release`, default settings). The machine was not idle (other jobs were running), so the spread matters as much as the median.

| Measured here | Go | Rust |
|---|---|---|
| Counting time, median of 15 runs | 249 ms (min 239, max 337) | 357 ms (min 321, max 465) |
| Binary size | 2,544,610 bytes | 445,600 bytes |
| Clean release build | 2.4 to 3.3 s (build cache cleared, 3 runs) | 0.3 to 0.9 s (`cargo clean`, 3 runs) |
| Peak memory (`/usr/bin/time -l`) | 167 to 207 MB (3 runs) | 81 MB (3 runs) |

The two build rows are not like for like. Clearing Go's build cache also forces the standard library to be compiled again, while Cargo links the precompiled standard library that rustup installs, so `cargo clean` only rebuilds my own small crate. Read them as "what I saw", not as a comparison of the compilers.

This is one microbenchmark. In this particular test Go counted faster and Rust used less memory and made a smaller binary. I did not profile why. One thing I did test: Rust's `HashMap` uses a DoS-resistant hasher by default. Swapping in a simple FNV hasher (written in about ten lines, in the `fnv` bin of the same project) gave a median of 214 ms over 11 runs, faster than both. So a default setting, not only the language, shaped that result. Change the task and the ranking can change. It says nothing about network services.

## Differences I am sure about

| | Go | Rust |
|---|---|---|
| Memory | Garbage collector, [pointers are safe but you do not own memory](/posts/go-pointers-memory/) | No GC; [ownership](/posts/rust-ownership/) and [borrowing](/posts/rust-borrowing-references/) are checked at compile time |
| Errors | [Values returned from functions](/posts/go-functions-defer-errors/), checked by convention | [`Result` and `?`](/posts/rust-error-handling-result/), part of the type, the compiler warns if ignored |
| Concurrency | [Goroutines and channels](/posts/go-goroutines-channels/) built into the language and runtime | OS threads in the standard library; async needs a runtime crate; data races are compile errors |
| Runtime | Ships a runtime (scheduler, GC) in every binary | No runtime to ship |

Things I believe but cannot prove here: Go compiles quickly for large projects and Rust usually compiles slower; Go's ecosystem for backend work is more settled, while Rust's is younger and growing fast. Check both against your own stack.

On learning curve, only my own experience counts. I was productive in Go in days. Rust took weeks before the compiler stopped surprising me, though the errors are very good teachers. Your background will change this.

## When to pick which

Go fits when you build network services, CLIs and internal tooling, and when the team must be productive fast. The language is small, the standard library covers HTTP, JSON and testing, and the [tooling](/posts/go-getting-started/) is one command. A garbage collector is a fine trade for most services.

Rust fits when you have hard latency or memory constraints and cannot afford GC pauses, when you target embedded or WebAssembly without a runtime, or when you write a library where correctness matters so much that you want the compiler to reject whole classes of bugs.

For most CRUD APIs, queue consumers and glue code, it does not matter much. Database, network and design quality dominate the language. Pick what your team can maintain.

## A few things to watch

- One microbenchmark is not evidence about your workload. Measure yours.
- Defaults matter: hasher, allocator, build profile and GC settings all change numbers.
- Run-to-run noise on a busy machine can exceed the difference between languages.
- "Faster" is rarely the real requirement; ask what latency, memory or hiring constraint you actually have.
- Both languages can be learned. I still pick Go for most services, and I am learning Rust to know when it is the better tool.

## What's next

The Rust series continues with closures and iterators. In the Go Backend series, the next post covers config, structured logging and errors in Go.
