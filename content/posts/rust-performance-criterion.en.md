+++
date = '2027-02-22T10:00:00+03:30'
draft = false
title = 'Performance and benchmarking with Criterion in Rust'
description = 'Benchmark Rust with Criterion: setup, BenchmarkGroup and BenchmarkId, black_box, reading the statistics, baselines and a comparison with Go testing.B.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "performance", "benchmarking", "criterion", "intermediate"]
cover = { image = "/images/covers/rust-performance-criterion.png", alt = "Performance and benchmarking with Criterion in Rust", hiddenInSingle = true }
+++

The [previous post](/posts/rust-unsafe-ffi/) was about `unsafe` and FFI. This one is about a question that comes right after "does it work": is it fast, and compared to what? A hand-rolled loop around `Instant::now()` gives you one number with no idea how noisy it is. **Criterion** is the standard statistics-driven benchmark crate for Rust. If you know Go, the counterparts are `testing.B` from [the testing post](/posts/go-testing-basics/), `benchstat`, and [pprof](/posts/go-profiling-pprof/). The [earlier Go vs Rust post](/posts/go-vs-rust-when-to-use/) already warned that one microbenchmark proves little; here is how to at least measure one properly.

> Rust 1.90, edition 2024, `criterion` 0.8.2, macOS arm64, local crate `strbench`. Timing numbers come from this machine and its load: I only started a run when the 1-minute load average was below 2 (starts at 1.7 to 1.99; one run ended at 2.5). Treat them as illustrative, not as a benchmark of your computer.

## Setup

Criterion is a dev-dependency, and each benchmark file needs `harness = false` so Criterion supplies `main` instead of libtest:

```toml
[dev-dependencies]
criterion = "0.8.2"

[[bench]]
name = "strings"
harness = false
```

`cargo bench` builds with the `bench` profile, which is optimized like `--release`. The code under test, two ways to build the same string:

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

A normal unit test checks that both return the same string for `n` of 0, 1, 10 and 1000; it passes. Check correctness before speed.

## A parameterized benchmark

`benches/strings.rs` uses a **BenchmarkGroup** and one **BenchmarkId** per implementation and size:

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

`cargo bench` first warms up for 3 seconds, then collects 100 samples. First run:

```text
build_string/grow/10    time:   [88.683 ns 88.900 ns 89.242 ns]
build_string/with_capacity/10   time: [28.566 ns 28.615 ns 28.669 ns]
build_string/grow/1000  time:   [776.62 ns 778.16 ns 779.80 ns]
build_string/with_capacity/1000 time: [392.20 ns 392.86 ns 393.53 ns]
build_string/grow/100000        time: [37.815 µs 37.879 µs 37.981 µs]
build_string/with_capacity/100000 time: [35.663 µs 35.736 µs 35.805 µs]
```

`[low estimate high]` is a confidence interval; the middle value is the best estimate. Pre-allocating was about 3x faster at n = 10, about 2x at n = 1000, and only a few percent at 100000, where copying dominates. Criterion also prints `Found 15 outliers among 100 measurements (15.00%)` with a high mild/severe breakdown, and a `thrpt:` line from `Throughput`. It printed `Gnuplot not found, using plotters backend`, so charts still work.

## When the compiler deletes your benchmark

```rust
c.bench_function("mix/result_dropped", |b| b.iter(|| { mix(black_box(1000)); }));
c.bench_function("mix/constant_input_8", |b| b.iter(|| mix(8)));
c.bench_function("mix/black_box_input_8", |b| b.iter(|| mix(black_box(8))));
c.bench_function("mix/honest_1000", |b| b.iter(|| mix(black_box(1000))));
```

`mix` is a pure xorshift loop. Results:

```text
mix/result_dropped      time:   [312.81 ps 312.93 ps 313.05 ps]
mix/constant_input_8    time:   [312.99 ps 313.20 ps 313.47 ps]
mix/black_box_input_8   time:   [3.5703 ns 3.5730 ns 3.5766 ns]
mix/honest_1000         time:   [1.8343 µs 1.8347 µs 1.8351 µs]
```

Roughly 0.3 nanoseconds means no work happened. In the first case I dropped the result, so the compiler removed the pure call. In the second, the constant input let it fold the loop at compile time. `std::hint::black_box` hides a value from the optimizer; `b.iter` also black-boxes whatever the closure returns. I did not inspect the assembly, this is my explanation of the numbers. Note that `criterion::black_box` is deprecated in 0.8.2 (the compiler warned me); use the std one.

## Reading the second run

Run the same command again and Criterion compares against the previous run in `target/criterion`:

```text
build_string/grow/1000  time:   [794.15 ns 799.88 ns 807.90 ns]
                        change: time: [+1.6851% +3.2524% +5.4679%] (p = 0.00 < 0.05)
                        Performance has regressed.
build_string/with_capacity/1000
                        change: time: [+0.0077% +0.4590% +1.1443%] (p = 0.12 > 0.05)
                        No change in performance detected.
```

The code did not change, yet two of six benchmarks said "regressed" (that one, and `with_capacity/100000`). On a laptop, a few percent of drift is normal, so do not treat one message as proof. The messages are `No change in performance detected`, `Change within noise threshold`, `Performance has regressed` and the improved counterpart.

For deliberate comparisons, name a baseline: `cargo bench -- --save-baseline before`, change the code, then `cargo bench -- --baseline before`. A trailing filter such as `"/1000"` selects benchmarks by name (it also matched `/100000`). An HTML report is generated at `target/criterion/report/index.html`.

## Compared to Go

Go's `testing.B` gives one line per run; you repeat with `-count` and compare files with `benchstat`. Criterion does the sampling, outlier counting and comparison in one `cargo bench`. The built-in `#[bench]` attribute exists only on nightly, so stable Rust effectively means Criterion (or similar crates). Criterion tells you how long; to find why, use a profiler such as `cargo flamegraph` or `perf`, which I only mention here.

## A few things to watch

- Benchmark only in the bench/release profile, never `cargo run` in debug.
- Sub-nanosecond results mean the work was deleted; use `black_box`.
- Quiet machine first: close other jobs and check `uptime`.
- One "regressed" message can be noise; repeat before believing it.
- Benchmark realistic input sizes; the winner can change with size.

## Exercise

1. Add a third implementation, `format!` per piece joined with `collect::<String>()`, and benchmark it at the same sizes.
2. Add sizes 100 and 10_000 to the `n` list and find where the gap between the two builders closes.

## What's next

Next: Futures, Pin and async internals in Rust.
