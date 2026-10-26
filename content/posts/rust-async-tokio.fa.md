+++
date = '2027-01-11T10:00:00+03:30'
draft = false
title = 'async/await و Tokio در Rust'
description = 'async/await و Tokio در Rust در عمل: future تنبل، spawn، join!، select!، timeout و لغو کار، Mutex ناهمگام و خطر کد blocking، همراه با خروجی واقعی.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "tokio", "intermediate"]
cover = { image = "/images/covers/rust-async-tokio.fa.png", alt = "async/await و Tokio در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-concurrency-threads/) از thread سیستم‌عامل استفاده کردیم. thread برای چند worker خوب است، اما سروری که منتظر هزاران socket است نمی‌خواهد برای هر انتظار یک thread داشته باشد. جواب این مشکل **async** است: تعداد زیادی task چند thread را بین خودشان تقسیم می‌کنند و وقتی منتظرند، نوبت را به دیگری می‌دهند. من به عنوان برنامه‌نویس Go مدام آن را با goroutine مقایسه می‌کردم؛ آخر مقاله، با احتیاط، همین کار را می‌کنم.

> همه‌ی کدها با Rust نسخه‌ی 1.90 و `tokio` نسخه‌ی 1.54.1 (با feature به نام `full`) کامپایل و اجرا شده‌اند. زمان‌ها روی لپ‌تاپ خودم و با load average حدود ۲ اندازه‌گیری شده‌اند، پس فقط تقریبی‌اند.

## Future تا await نشود کاری نمی‌کند

یک `async fn` بلافاصله یک **Future** برمی‌گرداند و بدنه‌اش شروع نمی‌شود. Rust اجراکننده‌ی داخلی ندارد و به یک crate برای **runtime** نیاز دارید. `#[tokio::main]` دور `main` یکی می‌سازد.

```rust
async fn greet(name: &str) -> String {
    println!("greet is running");
    tokio::time::sleep(Duration::from_millis(50)).await;
    format!("hello {name}")
}

#[tokio::main]
async fn main() {
    let fut = greet("Roham"); // هنوز چیزی چاپ نشده
    println!("future created");
    let msg = fut.await;      // حالا بدنه اجرا می‌شود
    println!("{msg}");

    greet("ignored");         // هرگز await نشده
    println!("done");
}
```

```text
warning: unused implementer of `Future` that must be used
  --> src/main.rs:16:5
   |
16 |     greet("ignored"); // never awaited: the body never runs
   |     ^^^^^^^^^^^^^^^^
   = note: futures do nothing unless you `.await` or poll them

future created
greet is running
hello Roham
done
```

«greet is running» فقط بعد از `fut.await` چاپ می‌شود و فراخوانی بی‌await اصلاً چیزی چاپ نمی‌کند. کامپایلر هم هشدار می‌دهد. وقتی کاری بی‌صدا انجام نمی‌شود، اول سراغ هشدارها بروید.

## spawn و join!

`tokio::spawn` یک future را به صورت task مستقل اجرا می‌کند و یک **JoinHandle** برمی‌گرداند؛ await کردنش `Result<T, JoinError>` می‌دهد. `tokio::join!` برعکس، چند future را هم‌زمان درون همین task اجرا می‌کند. سه کار ۲۰۰ میلی‌ثانیه‌ای را یک بار پشت سر هم await کردم و یک بار با `join!`:

```rust
let (a, b, c) = tokio::join!(job(1, 200), job(2, 200), job(3, 200));
```

```text
spawned result = 10
sequential: (10, 20, 30) in 607.132ms
join!:      (10, 20, 30) in 201.520583ms
```

اندازه‌گیری شده: حالت پشت سر هم تقریباً مجموع زمان‌ها را می‌گیرد و `join!` تقریباً بیشترینِ آن‌ها را.

## select!، timeout و لغو

`tokio::select!` منتظر اولین شاخه‌ای می‌ماند که تمام شود و بقیه را **drop** می‌کند. drop کردن یک future همان لغو آن است: دیگر هرگز اجرا نمی‌شود و متغیرهای محلی‌اش از بین می‌روند. با چاپ در `Drop` این موضوع دیده می‌شود:

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

«slow finished» هرگز چاپ نمی‌شود: بازنده در نقطه‌ی `.await` لغو شد. `tokio::time::timeout` همین ایده را بسته‌بندی می‌کند و `Err(Elapsed)` برمی‌گرداند. این معادل `select` با `time.After` و `context` در [مقاله‌ی sync، select و context در Go](/fa/posts/go-sync-select-context/) است، با این تفاوت که اینجا برای لغو به توکن نیازی نیست و drop کافی است.

## Channel و دو نوع Mutex

`tokio::sync::mpsc` همان channel ناهمگام است. سه task تولیدکننده هرکدام سه عدد فرستادند و یک مصرف‌کننده آن‌ها را زیر `tokio::sync::Mutex` جمع زد:

```text
received 9 messages: [100, 101, 102, 200, 201, 202, 300, 301, 302]
total = 1809
```

مصرف‌کننده guard ناهمگام را از روی یک `.await` (یعنی `yield_now`) نگه می‌دارد که مجاز است. همین کد با `std::sync::Mutex` رد می‌شود، چون یک task ممکن است روی thread دیگری ادامه پیدا کند و `MutexGuard` از نوع `Send` نیست:

```text
error: future cannot be sent between threads safely
  = help: ... the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
 10 |         tokio::task::yield_now().await; // guard still alive across await
    |                                  ^^^^^ await occurs here, with `mut g` maybe used later
```

اگر قفل را هرگز از روی `.await` نگه ندارید، mutex استاندارد مشکلی ندارد و سبک‌تر است.

## runtime را blocking نکنید

روی runtime از نوع `current_thread` فقط یک thread همه‌ی taskها را اجرا می‌کند. یک task ساعت‌مانند می‌خواهد هر ۱۰۰ میلی‌ثانیه چیزی چاپ کند، در حالی که `main` برای ۵۰۰ میلی‌ثانیه `std::thread::sleep` صدا می‌زند:

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

sleep مسدودکننده task ساعت را کاملاً فریز کرد و اولین tick بعد از پایان آن آمد. همان sleep داخل `tokio::task::spawn_blocking` (یک thread pool جدا) tickها را سر وقت نگه داشت.

## مقایسه با goroutine در Go

فقط چیزهایی که مطمئنم. scheduler در Go بخشی از runtime خود زبان است و `go f()` بدون هیچ چیز اضافه کار می‌کند؛ در Rust برای async به یک crate مثل Tokio نیاز دارید. تابع‌های async «رنگی» هستند: `async fn` را فقط از کد async می‌شود await کرد و این انتخاب در کل گراف فراخوانی پخش می‌شود، در حالی که تابع Go را بدون تغییر امضا هم می‌شود داخل goroutine صدا زد و هم بیرون آن.

## چند نکته‌ی مهم

- فراموش کردن `.await` فقط یک هشدار می‌دهد و کامپایل می‌شود؛ هشدارها را بخوانید.
- لغو در نقطه‌های `.await` اتفاق می‌افتد، پس پاک‌سازی را در `Drop` بگذارید نه بعد از یک await.
- نگه داشتن `MutexGuard` استاندارد از روی `.await` future را `!Send` می‌کند و `tokio::spawn` آن را نمی‌پذیرد.
- کد blocking (مثل `thread::sleep`، محاسبه‌ی سنگین CPU یا درایور هم‌گام فایل و دیتابیس) را مستقیم داخل task نزنید و از `spawn_blocking` استفاده کنید.
- `join!` هم‌زمانی درون یک task است؛ اگر می‌خواهید thread‌های دیگر هم کمک کنند از `spawn` استفاده کنید.

## تمرین

1. تابع `async fn fetch(id: u32) -> u32` را بنویسید که ۱۰۰ میلی‌ثانیه sleep می‌کند، ده تای آن را با `spawn` اجرا کنید و نتیجه‌ها را از `JoinHandle`ها جمع کنید.
2. یکی را با `tokio::time::timeout` به مدت ۵۰ میلی‌ثانیه بپیچید و خطا را چاپ کنید.
3. یک حلقه‌ی سنگین CPU را کنار یک ticker روی runtime از نوع `current_thread` اجرا کنید و بعد آن را به `spawn_blocking` ببرید.

## قدم بعدی

در مقاله‌ی بعد سراغ Serde و JSON در Rust می‌رویم: سریالایز و دیسریالایز کردن struct، همان کاری که در Go با `encoding/json` کردیم.
