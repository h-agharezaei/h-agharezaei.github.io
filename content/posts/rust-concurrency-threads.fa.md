+++
date = '2027-01-07T10:00:00+03:30'
draft = false
title = 'Concurrency با Thread در Rust'
description = 'Concurrency با thread در Rust: spawn و join، closure‌های move، کانال mpsc، Arc و Mutex، Send و Sync، scoped thread و تبدیل data race به خطای کامپایل.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "concurrency", "threads", "intermediate"]
cover = { image = "/images/covers/rust-concurrency-threads.fa.png", alt = "Concurrency با Thread در Rust", hiddenInSingle = true }
+++

دو thread را تصور کنید که هر کدام یکی به یک شمارنده‌ی مشترک اضافه می‌کنند. «یکی اضافه کن» یک قدم به نظر می‌رسد ولی ماشین سه کار می‌کند: مقدار فعلی را بخوان، یکی به آن اضافه کن، نتیجه را برگردان و بنویس. اگر هر دو thread مقدار `5` را بخوانند پیش از آنکه یکی‌شان بنویسد، هر دو `6` می‌نویسند و یکی از دو افزایش گم می‌شود. برنامه crash نمی‌کند و خطایی چاپ نمی‌کند؛ عدد فقط غلط است، و در هر اجرا جور دیگری غلط. به این باگ می‌گویند {{< term "data-race" "data race" >}}: دو thread که هم‌زمان به یک حافظه دست می‌زنند، دست‌کم یکی با نوشتن، و هیچ‌چیز هماهنگشان نمی‌کند. از سخت‌ترین باگ‌ها برای پیدا کردن است، چون کد درست به نظر می‌رسد.

جواب Rust این است که چنین برنامه‌ای را کامپایل نمی‌کند. قاعده‌هایی که از قبل می‌دانید، ownership و borrowing، دقیقاً همان چیزی است که لازم بود، و Rust به نتیجه‌اش می‌گوید «fearless concurrency» (هم‌زمانی بی‌ترس). این مقاله قدم‌به‌قدم می‌سازدش: شروع یک thread، دادن داده به آن، فرستادن پیام، به‌اشتراک‌گذاشتن وضعیت با قفل، و دو trait کوچک (`Send` و `Sync`) که ایراد کامپایلر را ممکن می‌کنند. فقط از کتابخانه‌ی استاندارد استفاده می‌کنیم و هر خطای کامپایلر پایین از یک کامپایل واقعی است. بعد از تست و مستندسازی در [مقاله‌ی قبل](/fa/posts/rust-testing-docs/) می‌آید. اگر Go می‌دانید، این مقاله هم‌ارز [goroutine و channel](/fa/posts/go-goroutines-channels/) و [sync و select و context](/fa/posts/go-sync-select-context/) است.

> همه‌چیز را با Rust نسخه‌ی 1.90 اجرا کرده‌ام (همان نسخه‌ی اجرای اول). برنامه‌هایی که از چند thread چاپ می‌کنند ممکن است در هر اجرا به ترتیب دیگری چاپ کنند؛ هر جا مهم بود گفته‌ام. چند برنامه‌ی کوچک (`move` یک عدد، و دو thread که یک شمارنده را تغییر می‌دهند) در demo اصلی نبودند؛ آن‌ها را برای همین مقاله نوشتم و جداگانه اجرا کردم. از پیام‌های خطا خط‌های «For more information…»، بعضی خط‌های `note:` و اشاره‌ها به سورس کتابخانه‌ی استاندارد را حذف کرده‌ام.

## شروع یک thread: spawn و join و panic

{{< term "os-thread" "thread" >}} یک خط اجرای مستقل داخل برنامه‌ی شماست. `thread::spawn` یک thread جدید سیستم‌عامل شروع می‌کند که یک closure را (در [مقاله‌ی closure‌ها](/fa/posts/rust-closures-iterators/) توضیح داده‌ام) هم‌زمان با بقیه‌ی کد شما اجرا می‌کند، و یک **`JoinHandle`** برمی‌گرداند. صدا زدن `join()` روی آن منتظر تمام‌شدن thread می‌ماند و یک `Result` برمی‌گرداند: `Ok` با مقدار برگشتی closure، یا `Err` اگر thread panic کرده باشد. demo یک thread سالم شروع می‌کند و یکی که عمداً panic می‌کند:

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

thread اول مجموع ۱ تا ۱۰ را برمی‌گرداند و `join` به ما `55` می‌دهد. thread دوم panic می‌کند و Rust پیام panic را چاپ می‌کند (روی stderr، پس در ترمینال ممکن است نسبت به خط‌های دیگر جای دیگری ظاهر شود). بعد `join` یک `Err` برمی‌گرداند و `match` ما خط آخر را چاپ می‌کند: panic در یک worker برنامه را نمی‌کشد. خودتان تصمیم می‌گیرید با `Err` چه کنید. (خط یادداشت `RUST_BACKTRACE` را حذف کرده‌ام.)

## چرا closure به move نیاز دارد

یک thread می‌تواند بعد از برگشتن تابعی که آن را ساخته به کار ادامه بدهد. پس اگر closure‌ی thread یک متغیر محلی را قرض بگیرد چه می‌شود؟

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

این همان reference معلق در [مقاله‌ی lifetime](/fa/posts/rust-lifetimes/) است. کامپایلر نمی‌داند که ما بلافاصله `join` می‌کنیم، و `v` وقتی `main` تمام شود drop می‌شود در حالی که thread ممکن است هنوز آن را بخواند. note می‌گوید `spawn` چه می‌خواهد: closure نباید چیزی را قرض بگیرد که ممکن است از بین برود (`'static`). help راه‌حل را می‌دهد: `move` بنویس تا thread صاحب `v` شود. بعد برنامه کامپایل می‌شود و `[1, 2, 3]` چاپ می‌کند.

یک غافلگیری درباره‌ی `move`: منتقل می‌کند، ولی برای نوع‌های ساده مثل عدد «منتقل‌کردن» یعنی کپی‌کردن. اگر یک شمارنده را به thread ببریم و آنجا زیادش کنیم:

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

thread مقدار خودش را تغییر داد و `main` هنوز `0` می‌بیند. این باگ Rust نیست، ولی نشان می‌دهد `move` به شما شمارنده‌ی مشترک نمی‌دهد. برای آن به ابزارهای بخش‌های بعد نیاز داریم.

## channel: فرستادن مقدار بین thread‌ها

ساده‌ترین راه امن برای همکاری thread‌ها این است که هیچ‌چیز را به اشتراک نگذارند: یک thread مقداری می‌فرستد و thread دیگر دریافت می‌کند. `std::sync::mpsc` («multiple producer, single consumer»، یعنی چند تولیدکننده و یک مصرف‌کننده) یک {{< term "mpsc-channel" "channel" >}} به شما می‌دهد: یک فرستنده (`tx`) و یک گیرنده (`rx`)، و فرستنده را برای هر thread تولیدکننده clone می‌کنید.

در این demo سه thread هر کدام دو پیام می‌فرستند و thread اصلی همه را جمع می‌کند:

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

به خط `drop(tx)` دقت کنید. حلقه‌ی گیرنده (`rx.iter()`) فقط وقتی تمام می‌شود که همه‌ی فرستنده‌ها drop شده باشند. سه clone وقتی thread‌هایشان تمام شوند از بین می‌روند، ولی `tx` اصلی هنوز در `main` است، پس دستی drop می‌کنیمش. اگر این خط را فراموش کنید حلقه تا ابد منتظر می‌ماند. پیام‌ها را قبل از چاپ مرتب کردم چون ترتیب تحویل از thread‌ها ثابت نیست؛ بدون مرتب‌سازی، خط‌ها ممکن است در هر اجرا به ترتیب دیگری بیایند.

فرستادن یک مقدار آن را منتقل می‌کند، پس فرستنده بعدش نمی‌تواند از آن استفاده کند:

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

همان قاعده‌ی همیشگی ownership است: بعد از `send(s)` رشته مال گیرنده است. اگر فرستنده می‌توانست به استفاده‌اش ادامه دهد، دو thread ممکن بود به یک رشته دست بزنند، که دقیقاً همان چیزی است که نمی‌خواهیم. پس «حافظه را با ارتباط‌گرفتن به اشتراک بگذار» اینجا را کامپایلر اجرا می‌کند، نه انضباط.

## وضعیت مشترک: چرا قفل، و Arc و Mutex

گاهی thread‌ها واقعاً باید یک داده را به اشتراک بگذارند، مثل شمارنده‌ی ما. آیا می‌شود فقط بگذاریم دو thread تغییرش بدهند؟ ببینیم کامپایلر چه می‌گوید (این نسخه از `thread::scope` استفاده می‌کند که پایین‌تر توضیح می‌دهم، تا closure‌ها بتوانند قرض بگیرند):

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

این همان قاعده‌ی borrowing است که می‌شناسید («در هر لحظه فقط یک reference تغییرپذیر») که حالا روی thread‌ها اعمال شده. هر closure یک قرض تغییرپذیر از `counter` می‌خواهد و کامپایلر به دومی «نه» می‌گوید. data race ابتدای مقاله اصلاً نوشتنی نیست. این مغز ایده است: data race فقط «دو دسترسی تغییرپذیر هم‌زمان» است که borrow checker از قبل ممنوعش کرده.

پس چطور شمارنده را عمداً به اشتراک بگذاریم؟ با نوعی که کارش امن کردن دسترسی است: **`Mutex`** (از «mutual exclusion»، یعنی انحصار متقابل). thread با `lock()` دسترسی انحصاری می‌گیرد و قفل وقتی guard برگشتی از scope بیرون برود خودکار آزاد می‌شود. در Rust داده داخل خود mutex است، پس بدون قفل کردن نمی‌توانید به آن برسید. `Mutex` را باید چند thread هم داشته باشند و هر thread باید یک دسته به آن داشته باشد. برای این از {{< term "arc" "Arc" >}} استفاده می‌کنیم، یک اشاره‌گر «شمارنده‌دارِ atomic»: نسخه‌ی thread-safe از `Rc` در [مقاله‌ی Smart Pointerها](/fa/posts/rust-smart-pointers/). با هم، `Arc<Mutex<T>>` داده‌ی مشترکِ قفل‌دار است:

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

هشت thread هر کدام هزار بار یکی اضافه می‌کنند و نتیجه دقیقاً ۸۰۰۰ است. هر thread یک clone از `Arc` می‌گیرد (دسته‌ی تازه‌ای به همان شمارنده)، `lock()` برای یک افزایش به آن دسترسی انحصاری می‌دهد، و guard در پایان همان دستور drop می‌شود که قفل را باز می‌کند. `lock()` یک `Result` برمی‌گرداند، برای همین `unwrap()` هست؛ بخش «مسمومیت mutex» پایین‌تر می‌گوید کِی ممکن است `Err` باشد.

## Send و Sync: کامپایلر از کجا می‌داند

کامپایلر از کجا می‌داند `Arc<Mutex<i32>>` در thread مشکلی ندارد و چیز دیگری دارد؟ به‌جای `Arc` از `Rc` استفاده کنید:

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

از پایین بخوانید. امضای `spawn` می‌گوید `F: Send + 'static`: closure‌ای که می‌گیرد باید {{< term "send-and-sync" "Send" >}} باشد. closure ما یک `Rc` دارد، و `Rc` نوع `Send` نیست، پس closure هم نیست. پیام دقیقاً همین را نشان می‌دهد.

`Send` و `Sync` دو **marker trait** هستند، یعنی trait‌هایی بدون متد که فقط یک نوع را برچسب می‌زنند. نوعی `Send` است که منتقل‌کردنش به thread دیگر امن باشد. نوعی `Sync` است که نگه‌داشتن یک reference مشترک (`&T`) به آن در چند thread هم‌زمان امن باشد. `Rc` شمارنده‌اش را بدون هیچ محافظتی تغییر می‌دهد، پس اگر دو thread آن را clone کنند، شمارش خراب می‌شود. برای همین نه `Send` است و نه `Sync`. `Arc` برای شمارنده از عملیات atomic استفاده می‌کند، پس هر دو است (به شرط اینکه داده‌ی داخلش هم باشد).

خودتان هیچ‌وقت `Send` یا `Sync` را نمی‌نویسید: کامپایلر آن‌ها را از روی فیلدهای نوع نتیجه می‌گیرد. struct وقتی `Send` است که همه‌ی فیلدهایش باشند. همین کل سازوکار است، و ارزش دارد ساده بگویمش: data race داده‌ی مشترکی می‌خواهد که بدون هماهنگی تغییر کند. ownership جلوی اشتراک را می‌گیرد، قاعده‌های borrow جلوی تغییر بدون هماهنگی را می‌گیرند، و `Send`/`Sync` نمی‌گذارند نوعی را که بین thread‌ها ناامن است قاچاقی وارد کنید. (کدی که داخل بلاک `unsafe` است هنوز می‌تواند قاعده‌ها را بشکند، ولی کد امن نمی‌تواند.)

## RwLock و atomic و thread‌های scope‌دار

سه ابزار دیگر از کتابخانه‌ی استاندارد. `RwLock` قفلی است که چند خواننده‌ی هم‌زمان یا یک نویسنده را قبول می‌کند. نوع atomic، مثل `AtomicUsize`، یک عملیات مثل «یکی اضافه کن» را تقسیم‌ناپذیر انجام می‌دهد و اصلاً قفل نمی‌خواهد، که ابزار درست برای یک شمارنده‌ی ساده است. demo چهار thread شروع می‌کند که هرکدام یک config مشترک را می‌خوانند و یکی به یک شمارنده‌ی مشترک اضافه می‌کنند، و بعد thread اصلی یک config جدید می‌نویسد:

```rust
let config = Arc::new(RwLock::new(String::from("v1")));
let hits = Arc::new(AtomicUsize::new(0));
// 4 thread: config.read().unwrap(); hits.fetch_add(1, Ordering::Relaxed);
// بعدش: *config.write().unwrap() = String::from("v2");
```

```text
hits = 4, config = v2
```

(برنامه‌ی کامل با حلقه‌ی ساخت thread‌ها در demo محلی است.) چهار hit شمرده شد و نوشتن config را به `v2` تغییر داد. آرگومان `Ordering` می‌گوید CPU چقدر باید ترتیب عملیات حافظه را دور عملیات atomic رعایت کند؛ `SeqCst` وقتی مطمئن نیستید امن‌ترین انتخاب است، و demo برای افزایش‌ها `Relaxed` را به کار می‌برد که برای یک شمارنده‌ی ساده کافی است.

ابزار آخر دردسر `move` و `Arc` را برای یک حالت رایج حل می‌کند. `thread::scope` تضمین می‌کند همه‌ی thread‌هایی که داخلش شروع شده‌اند پیش از برگشتنش تمام شده باشند، پس آن thread‌ها می‌توانند داده‌ی محلی را مستقیم قرض بگیرند، بدون `move` یا `Arc`:

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

وکتور به دو نیمه تقسیم می‌شود، هر نیمه در thread خودش جمع می‌شود، و بعدش `data` هنوز مال ماست. هر دو thread فقط می‌خوانند، پس اشتراک مشکلی ندارد. (در مثال شکست‌خورده‌ی بالا هر دو می‌خواستند بنویسند، برای همین آن کامپایل نشد.) همین ایده برای کار تکه‌تکه هم جواب می‌دهد: یک وکتور با ۱,۰۰۰,۰۰۰ عدد را به ۴ تکه تقسیم کردم، هر تکه را در یک thread scope‌دار جمع زدم و با جمع تک‌threadی مقایسه کردم. برنامه چاپ کرد `single = 500000500000, parallel = 500000500000, equal = true`. سرعت را اندازه نگرفتم، پس درباره‌اش ادعایی نمی‌کنم.

## مسمومیت mutex

اگر thread در حالی که قفل را دارد panic کند چه می‌شود؟ ممکن است داده نیمه‌به‌روز مانده باشد. Rust به‌عنوان هشدار mutex را **poisoned** (مسموم) علامت می‌زند. demo یک thread می‌سازد که mutex را قفل می‌کند و panic می‌کند، و بعد وضعیت را می‌پرسد:

```text
thread '<unnamed>' panicked at src/bin/poison.rs:9:9:
died while holding the lock
thread result is_err = true
is_poisoned = true
lock failed, but data is recoverable: 0
```

دو خط اول پیام panic از thread است. بعد: نتیجه‌ی thread یک `Err` بود (panic کرد)، mutex می‌گوید `is_poisoned = true`، و در نتیجه `lock()` هم `Err` برمی‌گرداند. این خطا بن‌بست نیست: `into_inner()` روی آن باز هم guard را به شما می‌دهد، پس اگر تصمیم بگیرید داده سالم است می‌توانید به استفاده‌اش ادامه دهید. اینجا `0` چاپ می‌شود، مقداری که داخلش بود.

## چیزهایی که Rust جلویشان را نمی‌گیرد

- **فراموش‌کردن `drop(tx)`** باعث می‌شود حلقه‌ی گیرنده تا ابد منتظر بماند، چون channel هیچ‌وقت بسته نمی‌شود.
- **نگه‌داشتن طولانی یک `MutexGuard`** باعث می‌شود thread‌هایتان در صف بایستند. بخش قفل‌شده را کوتاه نگه دارید.
- **deadlock و logic race هنوز ممکن‌اند.** Rust جلوی data race را می‌گیرد، نه deadlock را. قفل‌کردن دو mutex به ترتیب معکوس در دو thread هنوز می‌تواند همه‌چیز را قفل کند. «logic race» (نتیجه‌ی غلط به‌خاطر ترتیب عملیات، در حالی که هر دسترسی تنهایی امن است) هم ممکن است.
- **`unwrap()` روی `lock()`** در مثال‌ها اشکالی ندارد. در کد واقعی تصمیم بگیرید قفل مسموم برای برنامه‌تان چه معنایی دارد.
- **مقایسه با Go:** هر دو برای هم‌زمانی خوب‌اند. Rust data race را در زمان کامپایل رد می‌کند. Go آن‌ها را در زمان اجرا با فلگ `-race` پیدا می‌کند، و فقط روی مسیرهای کدی که واقعاً اجرا شوند.

## تمرین

۱. شمارنده را با `AtomicUsize` به‌جای `Mutex` بازنویسی کنید.
۲. یک استخر از ۳ worker بسازید که عددها را از یک channel بگیرند و مربعشان را روی channel دوم پس بفرستند. (راهنما: با `mpsc` فقط یک گیرنده هست، پس باید تصمیم بگیرید چطور آن را بین worker‌ها به اشتراک بگذارید.)

## قدم بعدی

thread یک منبع سیستم‌عامل است و وقتی هزاران کار دارید که بیشتر وقتشان منتظر شبکه یا دیسک می‌گذرد سنگین است. مقاله‌ی بعد، «async/await و Tokio در Rust»، همین مشکل را حل می‌کند.
