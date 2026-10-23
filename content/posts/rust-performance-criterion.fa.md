+++
date = '2027-02-22T10:00:00+03:30'
draft = false
title = 'پرفورمنس و benchmark با Criterion در Rust'
description = 'کد Rust را درست benchmark کنید: راه‌اندازی Criterion، BenchmarkGroup و BenchmarkId، black_box، خواندن خروجی آماری، baseline و مقایسه با testing.B در Go.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "performance", "benchmarking", "criterion", "intermediate"]
cover = { image = "/images/covers/rust-performance-criterion.fa.png", alt = "پرفورمنس و benchmark با Criterion در Rust", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/rust-unsafe-ffi/) درباره‌ی `unsafe` و FFI بود. این مقاله سؤالی را جواب می‌دهد که بعد از «کار می‌کند؟» می‌آید: سریع است، و نسبت به چه؟ یک حلقه‌ی دست‌ساز دور `Instant::now()` فقط یک عدد می‌دهد و نمی‌گوید چقدر نویزی است. **Criterion** کتاب‌خانه‌ی استاندارد benchmark آماری در Rust است. اگر Go بلدید، معادل‌هایش `testing.B` از [مقاله‌ی تست](/fa/posts/go-testing-basics/)، ابزار `benchstat` و [pprof](/fa/posts/go-profiling-pprof/) هستند. [مقاله‌ی مقایسه‌ی Go و Rust](/fa/posts/go-vs-rust-when-to-use/) هم قبلاً هشدار داده بود که یک microbenchmark چیز زیادی ثابت نمی‌کند؛ اینجا یاد می‌گیریم همان یکی را حداقل درست اندازه بگیریم.

> Rust 1.90، edition 2024، `criterion` نسخه‌ی 0.8.2، macOS روی arm64، و crate محلی `strbench`. اعداد زمانی مال همین ماشین و همین بار آن هستند: هر اجرا را فقط وقتی شروع کردم که load average یک‌دقیقه‌ای زیر ۲ بود (شروع‌ها بین ۱٫۷ و ۱٫۹۹؛ یک اجرا با ۲٫۵ تمام شد). آن‌ها را مثال بدانید، نه معیار کامپیوتر خودتان.

## راه‌اندازی

Criterion یک dev-dependency است و هر فایل benchmark باید `harness = false` داشته باشد تا Criterion به‌جای libtest تابع `main` را بسازد:

```toml
[dev-dependencies]
criterion = "0.8.2"

[[bench]]
name = "strings"
harness = false
```

`cargo bench` با پروفایل `bench` کامپایل می‌کند که مثل `--release` بهینه است. کدی که اندازه می‌گیریم، دو روش ساخت یک رشته‌ی یکسان:

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

یک تست معمولی برای `n` برابر ۰، ۱، ۱۰ و ۱۰۰۰ چک می‌کند که هر دو یک رشته برمی‌گردانند و پاس می‌شود. اول درستی، بعد سرعت.

## benchmark پارامتری

فایل `benches/strings.rs` از **BenchmarkGroup** و یک **BenchmarkId** برای هر پیاده‌سازی و هر اندازه استفاده می‌کند:

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

`cargo bench` اول ۳ ثانیه warm-up می‌کند و بعد ۱۰۰ نمونه جمع می‌کند. اجرای اول:

```text
build_string/grow/10    time:   [88.683 ns 88.900 ns 89.242 ns]
build_string/with_capacity/10   time: [28.566 ns 28.615 ns 28.669 ns]
build_string/grow/1000  time:   [776.62 ns 778.16 ns 779.80 ns]
build_string/with_capacity/1000 time: [392.20 ns 392.86 ns 393.53 ns]
build_string/grow/100000        time: [37.815 µs 37.879 µs 37.981 µs]
build_string/with_capacity/100000 time: [35.663 µs 35.736 µs 35.805 µs]
```

`[low estimate high]` یک بازه‌ی اطمینان است و عدد وسط بهترین تخمین. تخصیص از قبل برای `n = 10` حدود ۳ برابر، برای `n = 1000` حدود ۲ برابر و برای `n = 100000` فقط چند درصد سریع‌تر بود، چون آنجا کپی کردن غالب است. Criterion همچنین جمله‌ای مثل `Found 15 outliers among 100 measurements (15.00%)` با تفکیک high mild و severe چاپ می‌کند و از `Throughput` خط `thrpt:` می‌سازد. پیام `Gnuplot not found, using plotters backend` هم آمد، یعنی نمودارها باز هم ساخته می‌شوند.

## وقتی کامپایلر benchmark شما را حذف می‌کند

```rust
c.bench_function("mix/result_dropped", |b| b.iter(|| { mix(black_box(1000)); }));
c.bench_function("mix/constant_input_8", |b| b.iter(|| mix(8)));
c.bench_function("mix/black_box_input_8", |b| b.iter(|| mix(black_box(8))));
c.bench_function("mix/honest_1000", |b| b.iter(|| mix(black_box(1000))));
```

تابع `mix` یک حلقه‌ی xorshift خالص است. نتیجه:

```text
mix/result_dropped      time:   [312.81 ps 312.93 ps 313.05 ps]
mix/constant_input_8    time:   [312.99 ps 313.20 ps 313.47 ps]
mix/black_box_input_8   time:   [3.5703 ns 3.5730 ns 3.5766 ns]
mix/honest_1000         time:   [1.8343 µs 1.8347 µs 1.8351 µs]
```

حدود ۰٫۳ نانوثانیه یعنی هیچ کاری انجام نشده. در حالت اول نتیجه را دور ریختم و کامپایلر فراخوانی خالص را حذف کرد. در حالت دوم ورودی ثابت اجازه داد حلقه موقع کامپایل محاسبه شود. `std::hint::black_box` مقدار را از دید optimizer پنهان می‌کند و `b.iter` هم خروجی closure را black-box می‌کند. اسمبلی را بررسی نکردم؛ این توضیح من از روی اعداد است. نکته: `criterion::black_box` در نسخه‌ی 0.8.2 deprecated است (کامپایلر هشدار داد)، نسخه‌ی std را بگذارید.

## خواندن اجرای دوم

همان دستور را دوباره بزنید؛ Criterion با اجرای قبلی در `target/criterion` مقایسه می‌کند:

```text
build_string/grow/1000  time:   [794.15 ns 799.88 ns 807.90 ns]
                        change: time: [+1.6851% +3.2524% +5.4679%] (p = 0.00 < 0.05)
                        Performance has regressed.
build_string/with_capacity/1000
                        change: time: [+0.0077% +0.4590% +1.1443%] (p = 0.12 > 0.05)
                        No change in performance detected.
```

کد تغییر نکرده بود، ولی از شش benchmark دو تا «regressed» گفتند (این یکی و `with_capacity/100000`). روی لپ‌تاپ چند درصد نوسان عادی است، پس یک پیام را مدرک ندانید. پیام‌ها این‌هایند: `No change in performance detected`، `Change within noise threshold`، `Performance has regressed` و مشابه improved.

برای مقایسه‌ی عمدی یک baseline اسم‌دار بسازید: `cargo bench -- --save-baseline before`، کد را عوض کنید و بعد `cargo bench -- --baseline before`. یک فیلتر آخر دستور مثل `"/1000"` benchmarkها را با اسم انتخاب می‌کند (البته `/100000` را هم گرفت). گزارش HTML در `target/criterion/report/index.html` ساخته می‌شود.

## مقایسه با Go

`testing.B` در Go برای هر اجرا یک خط می‌دهد؛ با `-count` تکرار می‌کنید و فایل‌ها را با `benchstat` مقایسه می‌کنید. Criterion نمونه‌گیری، شمارش outlier و مقایسه را در یک `cargo bench` انجام می‌دهد. attribute داخلی `#[bench]` فقط روی nightly هست، پس در Rust پایدار عملاً سراغ Criterion (یا مشابهش) می‌روید. Criterion می‌گوید چقدر طول کشید؛ برای فهمیدن چرا از profiler مثل `cargo flamegraph` یا `perf` استفاده کنید که اینجا فقط اسمشان را می‌آورم.

## چند نکته‌ی مهم

- فقط در پروفایل bench/release اندازه بگیرید، نه با `cargo run` در debug.
- نتیجه‌ی زیر نانوثانیه یعنی کار حذف شده؛ از `black_box` استفاده کنید.
- اول ماشین را ساکت کنید: کارهای دیگر را ببندید و `uptime` را ببینید.
- یک پیام «regressed» می‌تواند نویز باشد؛ قبل از باور کردن تکرار کنید.
- با اندازه‌ی ورودی واقعی benchmark بگیرید؛ برنده با اندازه عوض می‌شود.

## تمرین

۱. پیاده‌سازی سوم را اضافه کنید: `format!` برای هر قطعه و `collect::<String>()`، و با همان اندازه‌ها benchmark بگیرید.
۲. اندازه‌های ۱۰۰ و ۱۰٬۰۰۰ را به لیست `n` اضافه کنید و ببینید فاصله‌ی دو روش از کجا از بین می‌رود.

## قدم بعدی

مقاله‌ی بعد: Futures، Pin و درون async در Rust.
