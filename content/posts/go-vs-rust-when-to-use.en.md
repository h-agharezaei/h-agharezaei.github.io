+++
date = '2026-12-26T10:00:00+03:30'
draft = false
title = 'Go or Rust? When to use which'
description = 'An honest Go vs Rust comparison from a backend engineer: one measured microbenchmark, a table of real differences, and a guide for when each language fits.'
contentType = 'analysis'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "comparison", "backend"]
cover = { image = "/images/covers/go-vs-rust-when-to-use.png", alt = "Go or Rust? When to use which", hiddenInSingle = true }
+++

"Should the next service be written in Go or in Rust?" It is a fair question, and any answer that comes without context deserves suspicion. Benchmarks that crown one language usually measure one task, on one machine, with one set of defaults. The honest answer starts with what you are building and who will maintain it.

I work mainly in Go and Node.js, and I am still learning Rust. So this post is one person's view with a little data, not a verdict. I have marked what I measured, what I am sure about as a documented fact, and what is only my own experience. After the series on [Go](/posts/go-getting-started/) and [Rust](/posts/rust-ownership/), this is the first place where the two languages meet.

To keep the discussion from being only opinion, I start with one small measurement. In it, Go counted faster, Rust used less than half the memory and produced a binary under a fifth the size, and swapping one default setting made Rust faster than both. The last part is the one I find most useful, because it shows how easy it is to compare defaults and believe you are comparing languages.

## One small measurement

The task is to count how often each word appears in a generated text of 10 million words. It is a typical "put things in a hash map and increment" job. The text has about 99,500 distinct words, and I wrote the program the obvious way in each language.

The text is generated inside each program by the same tiny **LCG** (a linear congruential generator, a pseudo-random number generator that fits in two lines). Both programs start from the same seed, so they build exactly the same text, and building the text is not part of the timing. Here is the core of each program:

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

Both loops split the text on whitespace and add one to the word's count in a {{< term "hash-table" "hash map" >}}. Both programs finish by printing the number of distinct words and the most frequent one. I re-ran both with Go 1.27 and Rust 1.90, and they printed the same line:

```text
distinct=99501 top=w2709:259
```

It says: 99,501 different words, and the most common one is `w2709`, which appears 259 times. Identical output from two languages is how I know they did the same work.

The timing table below is from my original run, with Go 1.26 and Rust 1.90 (`cargo build --release`, default settings) on one arm64 macOS laptop. The machine was not idle: other jobs were running. That is why I give the spread, not only the median. The **median** is the middle value of the runs, and it ignores a few unusually slow ones. When I re-ran the programs for this edit the machine was busy again, so I did not publish new timings.

| Measured in the original run | Go | Rust |
|---|---|---|
| Counting time, median of 15 runs | 249 ms (min 239, max 337) | 357 ms (min 321, max 465) |
| Binary size | 2,544,610 bytes | 445,600 bytes |
| Clean release build | 2.4 to 3.3 s (build cache cleared, 3 runs) | 0.3 to 0.9 s (`cargo clean`, 3 runs) |
| Peak memory (`/usr/bin/time -l`) | 167 to 207 MB (3 runs) | 81 MB (3 runs) |

(In the re-run the Rust release binary was again 445,600 bytes; the Go 1.27 binary was 2,482,114 bytes, so the Go size depends on the toolchain version.)

The two build rows are not like for like. Clearing Go's build cache also forces the standard library to be compiled again. Cargo, on the other hand, links the precompiled standard library that `rustup` installs, so `cargo clean` only rebuilds my own small crate. Read these rows as "what I saw", not as a comparison of the two compilers.

What does the table say? In this particular test Go counted faster, while Rust used less memory and made a smaller binary. I did not profile why, so I will not guess.

One thing I did test. By default, Rust's `HashMap` uses a {{< term "hash-collision" "hasher" >}} (the function that turns a key into a bucket number) that is designed to resist denial-of-service attacks, where someone sends keys chosen to collide. That safety has a cost. I swapped in a simple FNV hasher, about ten lines (it is the `fnv` binary in the same project, and its comment says it is not DoS-resistant). The median of 11 runs was 214 ms, which is faster than both of the first two. So a default setting, not only the language, shaped the result. Change the task and the ranking can change. And this test says nothing about network services.

## Differences I am sure about

Numbers are fragile. The following differences are documented design choices, not measurements:

| | Go | Rust |
|---|---|---|
| Memory | {{< term "garbage-collector" "Garbage collector" >}}, [pointers are safe but you do not own memory](/posts/go-pointers-memory/) | No GC; [ownership](/posts/rust-ownership/) and [borrowing](/posts/rust-borrowing-references/) are checked at compile time |
| Errors | [Values returned from functions](/posts/go-functions-defer-errors/), checked by convention | [`Result` and `?`](/posts/rust-error-handling-result/), part of the type, the compiler warns if ignored |
| Concurrency | [Goroutines and channels](/posts/go-goroutines-channels/) built into the language and runtime | OS threads in the standard library; async needs a runtime crate; data races are compile errors |
| Runtime | Ships a runtime (scheduler, GC) in every binary | No runtime to ship |

In short: Go makes memory and concurrency easy by doing work for you at run time. Rust asks you to prove things to the compiler first, and in return it has nothing to run behind your back.

There are also things I believe but cannot prove here: Go compiles quickly even for large projects while Rust usually compiles slower, and Go's ecosystem for backend work is more settled while Rust's is younger and growing fast. Check both against your own stack.

On the learning curve, only my own experience counts. I was productive in Go in days. Rust took weeks before the compiler stopped surprising me, though its error messages are very good teachers. Your background will change this.

## When to pick which

**Go fits** when you build network services, command-line tools and internal tooling, and when the team must become productive fast. The language is small, the standard library covers HTTP, JSON and testing, and the [tooling](/posts/go-getting-started/) is one command. For most services a garbage collector is a fine trade.

**Rust fits** when you have hard latency or memory limits and cannot afford the pauses a garbage collector may cause. It also fits when you target embedded devices or WebAssembly without a runtime, or when you write a library whose correctness matters so much that you want the compiler to reject whole classes of bugs.

For most CRUD APIs, queue consumers and glue code, the choice does not matter much. The database, the network and the quality of the design dominate the language. Pick what your team can maintain.

## Comparison traps

- One microbenchmark is not evidence about your workload. Measure your own.
- Defaults matter. The hasher above is one example; the allocator, the build profile and the GC settings also change numbers.
- Noise between runs on a busy machine can be larger than the difference between the languages. That is why the table shows min and max.
- "Faster" is rarely the real requirement. Ask what latency, memory or hiring constraint you actually have.
- Both languages can be learned. I still pick Go for most services, and I am learning Rust to know when it is the better tool.

## What's next

Next is "Go and Rust talking over gRPC". It stops comparing the two languages and makes them work together.
