+++
date = '2027-02-22T10:00:00+03:30'
draft = false
title = 'Performance and benchmarking with Criterion in Rust'
description = 'Benchmark Rust with Criterion: setup, BenchmarkGroup and BenchmarkId, black_box, reading the statistics, baselines and a comparison with Go testing.B.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "performance", "benchmarking", "criterion", "intermediate"]
cover = { image = "/images/covers/rust-performance-criterion.png", alt = "Performance and benchmarking with Criterion in Rust", hiddenInSingle = true }
+++

Suppose you want to know which of two ways of building a string is faster. The simplest thing is to run each once and take the time with a clock. But if you do it again, you get a different number: another program did something on the computer, the CPU was a little slower for a moment, a cache was empty. A single number does not tell you how far you can trust it.

And worse than noise, sometimes you are not measuring anything at all. If your benchmark reports about 0.3 nanoseconds, the compiler deleted the work and you are looking at the time of an empty loop. In this post we solve both problems with {{< term "criterion" "Criterion" >}}: it repeats the work many times, takes statistics from the samples, and tells you how noisy the result is. And we learn how to stop the work from being deleted.

This post follows [Unsafe and FFI](/posts/rust-unsafe-ffi/): there we wrote code that works, and now we ask how fast it is. If you know Go, the counterparts of Criterion are `testing.B` from [the testing post](/posts/go-testing-basics/), `benchstat`, and [pprof](/posts/go-profiling-pprof/). The [earlier Go vs Rust post](/posts/go-vs-rust-when-to-use/) already warned that one microbenchmark proves little; here we learn to at least measure one properly.

> Versions: Rust 1.90, edition 2024, `criterion` 0.8.2 (from the demo's `Cargo.lock`), macOS arm64, local crate `strbench`. **The timing numbers in this post are from the original run of the demo, not from a re-run.** In that run I started each benchmark only when the machine's 1-minute load average was below 2 (starts at 1.7 to 1.99; one run ended at 2.5). While preparing this version the machine's load average was between 5 and 10, so I did not re-measure the times; I only recompiled the demo, ran the tests, and counted memory allocations (which do not depend on machine load). Treat the numbers as illustrative, not as a benchmark of your computer.

## What does a benchmark measure?

The idea of Criterion is simple. You give it a small function (a closure) and say "measure the time of one run of this". Criterion first runs it for a few seconds to warm the machine up (caches fill, the CPU settles at a stable speed), and then collects 100 **samples**. Each sample is a batch of runs whose total time is measured. From the samples it estimates the time of one run and also gives a **confidence interval**: a range in which the true time lies with high probability (95% by default, according to Criterion's documentation). A narrow interval means the measurement was stable; a wide one means a lot of noise.

## The code under test

Two ways to build the same string, one growing gradually and one allocating in advance:

```rust
pub fn build_grow(n: usize) -> String {
    let mut s = String::new();
    for _ in 0..n { s += "ab"; }
    s
}

pub fn build_with_capacity(n: usize) -> String {
    let mut s = String::with_capacity(n * 2);
    for _ in 0..n { s.push_str("ab"); }
    s
}
```

Both build the string `ab` repeated `n` times. The first starts with an empty string and asks for more memory whenever it runs out of room. The second asks for the final size (`n * 2` bytes) at the start. Check correctness before speed: a normal unit test checks that both return the same string for `n` of 0, 1, 10 and 1000, and it passes.

Before any measurement we can guess why the first one is slower: it asks the system for memory several times. We can see this by counting, without a clock. A small separate program (in a temporary copy of the demo, not in the demo itself) installs a counting allocator and counts the memory requests:

```text
n = 10: grow = 3 allocations, with_capacity = 1
n = 1000: grow = 9 allocations, with_capacity = 1
n = 100000: grow = 16 allocations, with_capacity = 1
```

I ran these numbers again, in debug and in release, and they were the same. `with_capacity` always asks for memory once, but `grow` makes a new allocation or resize every time it runs out of room: 3 times for 20 bytes, 9 times for 2,000 bytes and 16 times for 200,000 bytes. The count grows slowly with size (not one-to-one), because the capacity is multiplied each time. So we expect the time difference to be more visible at small sizes, where allocation is a bigger part of the total work. Let us see whether the measurement says the same.

## Setup

Criterion is a dev-dependency, and each benchmark file needs `harness = false`. This means Rust's default test tool (libtest) is not used and Criterion supplies `main` itself:

```toml
[dev-dependencies]
criterion = "0.8.2"

[[bench]]
name = "strings"
harness = false
```

`cargo bench` builds with the `bench` profile, which is optimized like `--release`. Measuring debug code is meaningless, because debug is deliberately not optimized.

## A parameterized benchmark

We want to compare two methods at three input sizes. For this, `benches/strings.rs` creates a **BenchmarkGroup** (a group whose results are collected under one name) and gives one **BenchmarkId** for each combination of method and size:

```rust
use criterion::{BenchmarkId, Criterion, Throughput, criterion_group, criterion_main};
use std::hint::black_box;
use strbench::{build_grow, build_with_capacity};

fn bench_builders(c: &mut Criterion) {
    let mut group = c.benchmark_group("build_string");
    for n in [10usize, 1_000, 100_000] {
        group.throughput(Throughput::Bytes((n * 2) as u64));
        group.bench_with_input(BenchmarkId::new("grow", n), &n, |b, &n| {
            b.iter(|| build_grow(black_box(n)))
        });
        group.bench_with_input(BenchmarkId::new("with_capacity", n), &n, |b, &n| {
            b.iter(|| build_with_capacity(black_box(n)))
        });
    }
    group.finish();
}

criterion_group!(benches, bench_builders);
criterion_main!(benches);
```

`b.iter(|| ...)` is the closure whose time is taken. I explain {{< term "black-box" "black_box" >}} in the next section. `Throughput::Bytes` tells Criterion how many bytes each run produces, so that besides time it also reports a rate (bytes per second). `cargo bench` first warms up for 3 seconds and then collects 100 samples. This output is from the **first run**, on a machine with low load:

```text
build_string/grow/10    time:   [88.683 ns 88.900 ns 89.242 ns]
build_string/with_capacity/10   time: [28.566 ns 28.615 ns 28.669 ns]
build_string/grow/1000  time:   [776.62 ns 778.16 ns 779.80 ns]
build_string/with_capacity/1000 time: [392.20 ns 392.86 ns 393.53 ns]
build_string/grow/100000        time: [37.815 µs 37.879 µs 37.981 µs]
build_string/with_capacity/100000 time: [35.663 µs 35.736 µs 35.805 µs]
```

Each line is one benchmark: its name (group/method/size) and `time: [low middle high]`. The middle number is the best estimate and the two outer numbers are the ends of the confidence interval. The intervals here are very narrow (for example 88.7 to 89.2 nanoseconds), so the measurement was stable.

Now let us read it. For `n = 10`, `with_capacity` at 28.6 ns versus 88.9 ns was about 3 times faster. For `n = 1000` about 2 times (392.9 versus 778.2). For `n = 100000` only a few percent (35.7 versus 37.9 microseconds), because there copying 200 thousand bytes dominates and allocations are a small part. This is what the allocation count led us to expect: the winner is the one that asks for less memory, but as the input grows the gap shrinks.

Criterion prints other things too. For example `Found 15 outliers among 100 measurements (15.00%)` with a `high mild` / `high severe` breakdown: an **outlier** is a sample far from the rest (usually because something else ran on the machine at that moment). From `Throughput` it also makes a `thrpt:` line. It also printed `Gnuplot not found, using plotters backend`: gnuplot was not installed, but charts are still generated.

## When the compiler deletes your benchmark

Now the first problem from the start of the post. If an optimizing compiler sees that the result of a computation is never used, it may throw the whole computation away. If the input is also a constant, it may compute the result at compile time and leave just a ready number at run time. In both cases your benchmark measures nothing. The function `mix` is a pure xorshift loop (it takes a number and returns a number), and I tried four versions of its benchmark:

```rust
c.bench_function("mix/result_dropped", |b| b.iter(|| { mix(black_box(1000)); }));
c.bench_function("mix/constant_input_8", |b| b.iter(|| mix(8)));
c.bench_function("mix/black_box_input_8", |b| b.iter(|| mix(black_box(8))));
c.bench_function("mix/honest_1000", |b| b.iter(|| mix(black_box(1000))));
```

```text
mix/result_dropped      time:   [312.81 ps 312.93 ps 313.05 ps]
mix/constant_input_8    time:   [312.99 ps 313.20 ps 313.47 ps]
mix/black_box_input_8   time:   [3.5703 ns 3.5730 ns 3.5766 ns]
mix/honest_1000         time:   [1.8343 µs 1.8347 µs 1.8351 µs]
```

The unit `ps` is a picosecond: 0.3 nanoseconds. No loop of 1000 iterations is that fast, so no work was done. Case one: I dropped the result (the `;` after `mix(...)`), and because `mix` is pure, the compiler removed the call itself. Case two: the input is the constant 8 and the small loop was solved at compile time. Both gave about 0.313 nanoseconds; probably both measured only the overhead of the benchmark loop itself. Case three, with the input hidden, was 3.57 nanoseconds, and case four, `honest`, with 1000 iterations, was 1.835 microseconds.

The fix is `std::hint::black_box`: it makes the value passing through it "unknown" to the optimizer, so it cannot assume what the value is. `b.iter` also black-boxes the closure's return value, so returning the result (without `;`) is enough. I did not inspect the assembly; the explanation of why it was deleted comes from the numbers, not from machine code. One version note: `criterion::black_box` is deprecated in 0.8.2. I compiled it again and the compiler warned "use `std::hint::black_box()` instead". Use the std version.

## Reading the second run

Run the same command again; Criterion compares the result with the previous run in `target/criterion`. This is part of the output of the second run of the original session:

```text
build_string/grow/1000  time:   [794.15 ns 799.88 ns 807.90 ns]
                        change: time: [+1.6851% +3.2524% +5.4679%] (p = 0.00 < 0.05)
                        Performance has regressed.
build_string/with_capacity/1000
                        change: time: [+0.0077% +0.4590% +1.1443%] (p = 0.12 > 0.05)
                        No change in performance detected.
```

The `change` line shows the relative change since the previous run, with its interval, and `p` says how likely it would be to see such a difference if nothing had actually changed. If `p` is below 0.05, Criterion considers the change significant. The first case has `p = 0.00` and says `Performance has regressed` (slower); the second has `p = 0.12` and says `No change in performance detected`.

But notice: **the code had not changed**. Of six benchmarks, two said "regressed" (this one, and `with_capacity/100000`). On a laptop a few percent of drift is normal, because the CPU, the temperature and other programs change all the time. The statistics only say "the difference in these measurements is not noise", not that the code became slower. So do not treat one message as proof. The possible messages are `No change in performance detected`, `Change within noise threshold`, `Performance has regressed` and the improved counterpart.

For deliberate comparisons, name a baseline. `cargo bench -- --save-baseline before` saves the result under the name `before`. Then change the code and run `cargo bench -- --baseline before` to compare against it. A trailing filter such as `"/1000"` selects benchmarks by name (note that it also matches `/100000`, because the filter works on part of the name). An HTML report is generated at `target/criterion/report/index.html`.

## Compared to Go

Go's `testing.B` gives one line per run. For statistics you repeat with `-count` and compare files with `benchstat`. Criterion does the sampling, outlier counting and comparison in one `cargo bench`. The built-in `#[bench]` attribute works only on nightly, so on stable Rust you effectively reach for Criterion (or a similar tool). Criterion tells you how long something took; to find out **why**, use a profiler such as `cargo flamegraph` or `perf`, which I only mention here.

## When a benchmark lies

- **Measure with the bench or release profile**, not with `cargo run` in debug, because debug code is deliberately slow and says nothing about the real program.
- **A time below a nanosecond means the work was deleted.** Use `black_box` for the input and return the result.
- **Quiet the machine first.** Close other jobs and look at `uptime`; high load widens the intervals and makes the numbers meaningless. (That is why this post has no new numbers.)
- **One "regressed" message can be noise.** Repeat before believing it.
- **Benchmark with realistic input sizes.** The winner changes with size, like `grow` and `with_capacity` above.

## Exercise

1. Add a third implementation, `format!` per piece joined with `collect::<String>()`, and benchmark it at the same sizes.
2. Add sizes 100 and 10,000 to the `n` list and find where the gap between the two builders closes.

## What's next

"Futures, Pin and async internals in Rust" opens the box under async/await: what a future is, who polls it, and why `Pin` is everywhere.
