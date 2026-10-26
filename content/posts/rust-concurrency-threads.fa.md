+++
date = '2027-01-07T10:00:00+03:30'
draft = false
title = 'Concurrency با Thread در Rust'
description = 'Concurrency با thread در Rust: spawn و join، closure‌های move، کانال mpsc، Arc و Mutex، Send و Sync، scoped thread و تبدیل data race به خطای کامپایل.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "concurrency", "threads", "intermediate"]
cover = { image = "/images/covers/rust-concurrency-threads.fa.png", alt = "Concurrency با Thread در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-testing-docs/) درباره‌ی تست و مستندسازی صحبت کردیم. حالا سراغ قابلیتی می‌رویم که Rust بیشترین افتخار را به آن می‌کند: «concurrency بدون ترس». ادعا این است که همان **ownership** و **borrowing** که می‌شناسید، **data race** را هم در زمان کامپایل غیرممکن می‌کند. فقط از کتاب‌خانه‌ی استاندارد استفاده می‌کنیم و همه‌ی خطاهای زیر از کامپایل واقعی آمده‌اند. اگر Go بلدید، این بخش معادل [goroutine و channel](/fa/posts/go-goroutines-channels/) و [sync، select و context](/fa/posts/go-sync-select-context/) است.

> همه‌ی کدها با Rust نسخه‌ی 1.90 اجرا شده‌اند.

## spawn، join و panic

تابع `thread::spawn` یک thread سیستم‌عامل می‌سازد و یک **JoinHandle** برمی‌گرداند. فراخوانی `join()` منتظر پایان thread می‌ماند و یک `Result` می‌دهد: `Ok` همراه مقدار برگشتی، یا `Err` اگر thread دچار panic شده باشد.

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

panic در یک worker کل برنامه را نمی‌کشد و شما تصمیم می‌گیرید با `Err` چه کنید.

## چرا closure به move نیاز دارد

thread ساخته‌شده ممکن است از تابعِ سازنده‌اش بیشتر عمر کند، پس نمی‌تواند متغیرهای محلی را borrow کند:

```text
error[E0373]: closure may outlive the current function, but it borrows `v`, which is owned by the current function
5 |     let h = thread::spawn(|| println!("{v:?}"));
  |                           ^^            - `v` is borrowed here
  |                           |
  |                           may outlive borrowed value `v`
help: to force the closure to take ownership of `v` (and any other referenced variables), use the `move` keyword
```

با نوشتن `move ||` مالکیت `v` به thread داده می‌شود؛ آن‌وقت کد کامپایل می‌شود و `[1, 2, 3]` چاپ می‌کند.

## Channel: جابه‌جایی مالکیت بین threadها

`std::sync::mpsc` یعنی چند تولیدکننده و یک مصرف‌کننده. برای هر تولیدکننده sender را clone کنید. به `drop(tx)` دقت کنید: گیرنده تا وقتی همه‌ی senderها، از جمله اصلی، از بین نروند منتظر می‌ماند.

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

پیام‌ها را مرتب کردم چون ترتیب رسیدن بین threadها ثابت نیست. فرستادن یک مقدار آن را move می‌کند، پس فرستنده بعد از آن نمی‌تواند به آن دست بزند:

```text
error[E0382]: borrow of moved value: `s`
8 |         tx.send(s).unwrap();
  |                 - value moved here
9 |         println!("{s}");
  |                    ^ value borrowed here after move
```

این همان «حافظه را با ارتباط به اشتراک بگذار» است، اما با اجبار کامپایلر.

## حالت مشترک: Arc و Mutex

وقتی threadها باید داده‌ی مشترک داشته باشند، از `Arc<Mutex<T>>` استفاده کنید. **Arc** یک اشاره‌گر شمارنده‌دار با شمارش اتمی است، یعنی نسخه‌ی thread-safe از `Rc`. **Mutex** با `lock()` دسترسی انحصاری می‌دهد.

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

هشت thread، هرکدام هزار افزایش، و نتیجه دقیقاً 8000 است. قفل وقتی guard از scope خارج شود آزاد می‌شود.

## Send و Sync: data race چطور به خطای کامپایل تبدیل می‌شود

اگر به‌جای `Arc` از `Rc` استفاده کنیم چه می‌شود؟

```text
error[E0277]: `Rc<std::sync::Mutex<i32>>` cannot be sent between threads safely
  |
  = help: within `{closure@src/bin/rc_mutex.rs:8:27: 8:34}`, the trait `Send` is not implemented for `Rc<std::sync::Mutex<i32>>`
note: required by a bound in `spawn`
726 |     F: Send + 'static,
```

دو trait نشانگر این را توضیح می‌دهند. نوعی **Send** است که انتقالش به thread دیگر امن باشد. نوعی **Sync** است که اشتراکش با reference بین threadها امن باشد (یعنی `&T` از نوع Send باشد). `Rc` شمارنده‌اش را بدون عملیات اتمی تغییر می‌دهد، پس هیچ‌کدام نیست. تابع `spawn` شرط `Send` می‌گذارد و کامپایلر آن را خودکار از فیلدها نتیجه می‌گیرد. کل سازوکار همین است: data race به تغییرِ هم‌زمانِ بدون هماهنگی نیاز دارد و سیستم نوع اجازه‌ی نوشتنش را نمی‌دهد. درباره‌ی `Rc` بیشتر در [اشاره‌گرهای هوشمند](/fa/posts/rust-smart-pointers/) آمده است.

## RwLock، atomic و scoped thread

`RwLock` چند خواننده یا یک نویسنده را اجازه می‌دهد. برای شمارنده‌ی ساده، `AtomicUsize` اصلاً قفل لازم ندارد:

```rust
let config = Arc::new(RwLock::new(String::from("v1")));
let hits = Arc::new(AtomicUsize::new(0));
// 4 threads: config.read().unwrap(); hits.fetch_add(1, Ordering::Relaxed);
// afterwards: *config.write().unwrap() = String::from("v2");
```

```text
hits = 4, config = v2
```

(برنامه‌ی کامل همراه حلقه‌ی ساخت threadها در دمو‌ی محلی من هست.) آرگومان `Ordering` ترتیب حافظه را تعیین می‌کند؛ وقتی مطمئن نیستید `SeqCst` انتخاب امن است.

`thread::scope` تضمین می‌کند threadهایش پیش از بازگشت تمام شوند، پس می‌توانند بدون `move` و `Arc` داده‌ی محلی را borrow کنند:

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

همین ایده برای کار تکه‌تکه هم جواب می‌دهد: یک vector با 1,000,000 عدد را به 4 تکه تقسیم کردم، هر تکه را در یک scoped thread جمع زدم و با جمع تک‌threadی مقایسه کردم. هر دو 500000500000 شدند. سرعت را اندازه نگرفتم، پس درباره‌اش ادعایی نمی‌کنم.

## Mutex poisoning

اگر threadی در حالی که قفل را دارد دچار panic شود، mutex به حالت **poisoned** درمی‌آید؛ هشداری که می‌گوید ممکن است داده نیمه‌کاره به‌روز شده باشد:

```text
thread result is_err = true
is_poisoned = true
lock failed, but data is recoverable: 0
```

`lock()` یک `Err` برمی‌گرداند و اگر تصمیم بگیرید داده سالم است، `into_inner()` روی همان خطا باز هم guard را می‌دهد.

## چند نکته که باید حواستان باشد

- فراموش کردن `drop(tx)` باعث می‌شود حلقه‌ی گیرنده تا ابد منتظر بماند.
- نگه داشتن طولانی `MutexGuard` threadها را پشت سر هم می‌اندازد؛ بخش بحرانی را کوتاه نگه دارید.
- Rust جلوی data race را می‌گیرد، نه deadlock و نه خطای منطقیِ ترتیب را. قفل کردن دو mutex با ترتیب معکوس باز هم گیر می‌کند.
- `unwrap()` روی `lock()` در مثال‌ها خوب است، اما در کد واقعی عمداً تصمیم بگیرید قفل poisoned یعنی چه.
- مقایسه با Go: هر دو برای concurrency خوب‌اند. Rust data race را در زمان کامپایل رد می‌کند؛ Go آن را در زمان اجرا با فلگ `-race` پیدا می‌کند و فقط روی مسیرهایی که واقعاً اجرا شوند.

## تمرین

1. شمارنده را به‌جای `Mutex` با `AtomicUsize` بنویسید.
2. یک pool با 3 worker بسازید که اعداد را از یک channel بگیرند و مربعشان را روی channel دوم بفرستند.

## قدم بعدی

وقتی هزاران کار هم‌زمان دارید که بیشترشان منتظر I/O هستند، thread سنگین است. در مقاله‌ی بعد سراغ async/await و Tokio در Rust می‌رویم.
