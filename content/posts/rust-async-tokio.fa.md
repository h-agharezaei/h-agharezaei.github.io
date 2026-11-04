+++
date = '2027-01-11T10:00:00+03:30'
draft = false
title = 'async/await و Tokio در Rust'
description = 'async/await و Tokio در Rust در عمل: future تنبل، spawn، join!، select!، timeout و لغو کار، Mutex ناهمگام و خطر کد blocking، همراه با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "tokio", "intermediate"]
cover = { image = "/images/covers/rust-async-tokio.fa.png", alt = "async/await و Tokio در Rust", hiddenInSingle = true }
+++

سروری را در نظر بگیرید که ده هزار اتصال باز دارد. تقریباً همه‌ی آن‌ها در هر لحظه کاری نمی‌کنند: هر کدام منتظر است طرف مقابل یک بایت بفرستد یا پایگاه داده جواب بدهد. اگر مثل [مقاله‌ی قبل](/fa/posts/rust-concurrency-threads/) به هر اتصال یک thread سیستم‌عامل بدهید، ده هزار thread دارید که تقریباً تمام وقتشان خوابیده‌اند و هرکدام حافظه و کار زمان‌بندی می‌خواهد. کمی شبیه این است که برای هر میز یک گارسون استخدام کنید و هر گارسون کنار میزش بایستد تا غذا آماده شود.

**async** راه دیگر است: یک گارسون به چند میز رسیدگی می‌کند و وقتی یک میز منتظر غذاست، به سراغ میز دیگری می‌رود. به زبان برنامه: چند task روی چند thread محدود شریک‌اند و taskی که باید منتظر بماند کنار می‌رود تا thread کار دیگری را اجرا کند. من به‌عنوان برنامه‌نویس Go مدام این را با goroutine مقایسه می‌کردم، و آخر مقاله با احتیاط همین کار را می‌کنم.

مقاله از ایده‌ای شروع می‌کند که همه را غافلگیر می‌کند (یک تابع async تا await نشود کاری نمی‌کند)، بعد اجرای هم‌زمان چند task، لغو کردنشان، به اشتراک گذاشتن داده بینشان، و اشتباه بزرگی که باید از آن دوری کرد: مسدود کردن thread.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 و `tokio` نسخه‌ی 1.54.1 (قابلیت `full`) کامپایل و اجرا شده‌اند. همه‌ی demo‌ها را برای این نسخه‌ی مقاله دوباره اجرا کردم و خروجی‌ها یکسان بود. زمان‌ها (در بخش‌های `join!` و مسدود کردن thread) همان عددهای اجرای اول‌اند، که روی لپ‌تاپم با میانگین بار یک‌دقیقه‌ای حدود ۲ ثبت کردم؛ اجرای دوباره‌ی من روی ماشینی شلوغ‌تر انجام شد و همان الگو را با میلی‌ثانیه‌های کمی متفاوت داد، پس همه‌ی زمان‌ها را تقریبی بخوانید. برنامه‌هایی که از چند task چاپ می‌کنند ممکن است ترتیب دیگری داشته باشند. خط‌های «For more information…» و خط‌های `note:` را که به پوشه‌ی home اشاره می‌کردند حذف کرده‌ام.

## future تا await نشود کاری نمی‌کند

کلمه‌ی `async` را جلوی یک تابع بگذارید و معنایش عوض می‌شود. صدا زدنش دیگر بدنه را اجرا نمی‌کند. یک **future** برمی‌گرداند، یعنی مقداری که «کاری را نشان می‌دهد که هنوز انجام نشده». بدنه فقط وقتی اجرا می‌شود که کسی آن future را با `.await` بخواهد. future را مثل یک سفارش نوشته‌شده تصور کنید: تا آشپزخانه آن را برندارد چیزی پخته نمی‌شود.

کتابخانه‌ی استاندارد Rust «آشپزخانه»ای که futureها را اجرا کند ندارد، به آن می‌گویند **executor** یا **runtime**، پس یک crate برایش اضافه می‌کنید. {{< term "tokio" "Tokio" >}} رایج‌ترین آن‌هاست. attribute به اسم `#[tokio::main]` یک runtime از Tokio دور `main` می‌سازد تا خود `main` هم بتواند `async` باشد. یک برنامه‌ی کوچک که تنبلی را نشان می‌دهد:

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

    greet("ignored");         // هیچ‌وقت await نمی‌شود
    println!("done");
}
```

```text
warning: unused implementer of `Future` that must be used
  --> src/main.rs:16:5
   |
16 |     greet("ignored"); // never awaited: the body never runs
   |     ^^^^^^^^^^^^^^^^
   |
   = note: futures do nothing unless you `.await` or poll them
   = note: `#[warn(unused_must_use)]` on by default

future created
greet is running
hello Roham
done
```

خروجی را به ترتیب بخوانید. `let fut = greet("Roham")` تابع را صدا می‌زند ولی «greet is running» چاپ نمی‌شود. یک {{< term "rust-future" "future" >}} می‌گیریم و بس. پس «future created» اول می‌آید. فقط وقتی `fut.await` را می‌نویسیم بدنه شروع می‌شود: «greet is running»، بعد خواب ۵۰ میلی‌ثانیه‌ای، بعد `hello Roham`. آخرین فراخوانی، `greet("ignored")`، یک future می‌سازد و بدون await دورش می‌اندازد، پس بدنه‌اش هرگز اجرا نمی‌شود: «greet is running» دوم وجود ندارد. کامپایلر بالای خروجی هشدار می‌دهد (این هشدار هنگام کامپایل چاپ می‌شود، پیش از شروع برنامه)، که یادآوری خوبی است برای دفعه‌ی بعد که در کد async چیزی بی‌صدا انجام نمی‌شود.

`.await` واقعاً چه می‌کند؟ داخل یک تابع async، `.await` یعنی: «تا این future آماده نشود نمی‌توانم ادامه بدهم. اگر هنوز آماده نیست، مرا نگه دار و بگذار thread کار دیگری بکند، و وقتی آماده شد برگرد.» نقطه‌ای که یک task می‌تواند مکث کند همیشه یک `.await` است و هیچ جای دیگر. کد بین دو `.await` بدون وقفه اجرا می‌شود. ایده‌ی پشت همه‌ی بخش‌های بعدی همین است. (در پشت صحنه runtime مدام با صدا زدن متدی به اسم `poll` از future می‌پرسد «تمام شدی؟»؛ تقریباً هیچ‌وقت خودتان آن را صدا نمی‌زنید و یک مقاله‌ی بعدی این مجموعه دقیق‌تر به آن می‌پردازد.)

## spawn و join!

await کردن futureها پشت سر هم یعنی ترتیبی: دومی وقتی شروع می‌شود که اولی تمام شود. برای اینکه چند کار هم‌زمان پیش بروند دو ابزار هست. `tokio::spawn` یک future را به‌عنوان **task** مستقل شروع می‌کند که runtime می‌تواند آن را روی هر یک از thread‌هایش اجرا کند، و یک `JoinHandle` برمی‌گرداند؛ await کردن handle یک `Result<T, JoinError>` می‌دهد (اگر task panic کرده باشد `Err`). `tokio::join!` چند future را هم‌زمان داخل task فعلی اجرا می‌کند و منتظر همه‌شان می‌ماند.

demo یک تابع `job` دارد که می‌خوابد و `id * 10` برمی‌گرداند. اول یک job با `spawn`، بعد سه job دویست‌میلی‌ثانیه‌ای پشت سر هم await می‌شوند، و بعد همان سه تا با `join!`:

```rust
let (a, b, c) = tokio::join!(job(1, 200), job(2, 200), job(3, 200));
```

```text
spawned result = 10
sequential: (10, 20, 30) in 607.132ms
join!:      (10, 20, 30) in 201.520583ms
```

(خط‌های زمان‌دار از اجرای اول‌اند، همان‌طور که بالا گفتم.) نتیجه در هر دو یکی است. زمان نه: await یکی‌یکی مجموع انتظارها را می‌گیرد، حدود ۶۰۰ میلی‌ثانیه. با `join!` هر سه خواب هم‌زمان پیش می‌روند، پس کل زمان حدود طولانی‌ترین‌شان است، ۲۰۰ میلی‌ثانیه. برای این کار thread اضافه‌ای لازم نشد؛ سه انتظار فقط روی هم افتادند.

## select! و timeout و لغو کردن

اغلب می‌خواهید «هر کدام زودتر تمام شد». `tokio::select!` منتظر اولین شاخه‌ای می‌ماند که تمام شود و بقیه را **drop** می‌کند. drop کردن یک future راه لغو کردنش در Rust ناهم‌گام است: future دیگر هرگز اجرا نمی‌شود و متغیرهای محلی‌اش نابود می‌شوند. این همان {{< term "task-cancellation" "لغو با drop" >}} است. برای دیدنش، هر job به اسم `slow` در demo مقدار کوچکی نگه می‌دارد که وقتی drop شود یک خط چاپ می‌کند:

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

سه آزمایش، به ترتیب:

- در `select!` اول، `fast` (۵۰ میلی‌ثانیه) از `slow` (۵۰۰ میلی‌ثانیه) جلو می‌زند. «fast finished» را می‌بینیم، بعد هر دو مقدار drop می‌شوند و برنده اعلام می‌شود. خط «slow finished» هرگز نمی‌آید: `slow` وقتی هنوز در `.await` خودش خواب بود لغو شد و فقط پیام drop آن اجرا شد.
- در دومی شاخه‌ی دوم یک تایمر ساده‌ی ۱۰۰ میلی‌ثانیه‌ای است. تایمر برنده می‌شود، «timed out» چاپ می‌شود و `work` پانصد میلی‌ثانیه‌ای لغو می‌شود («work dropped»).
- سومی از `tokio::time::timeout` استفاده می‌کند، نسخه‌ی آماده‌ی همین ایده. اگر مهلت بگذرد `Err(Elapsed)` برمی‌گرداند. job کند دوباره drop می‌شود و خطا به شکل `deadline has elapsed` چاپ می‌شود.

این همتای `select` با `time.After` و `context` در [مقاله‌ی sync و select و context در Go](/fa/posts/go-sync-select-context/) است. تفاوتش این است که لغو اینجا نیازی به توکنی که دست‌به‌دست شود ندارد: drop کردن future کافی است.

## channel و دو Mutex

task‌ها هم مثل thread‌ها می‌توانند پیام بفرستند. `tokio::sync::mpsc` channel ناهم‌گام است: فرستادن و گرفتن `.await` می‌شوند، پس task بدون مسدود کردن thread منتظر می‌ماند. در demo سه task تولیدکننده هر کدام سه عدد می‌فرستند و یک task مصرف‌کننده آن‌ها را می‌گیرد و در مجموعی جمع می‌کند که با `tokio::sync::Mutex` محافظت می‌شود:

```text
received 9 messages: [100, 101, 102, 200, 201, 202, 300, 301, 302]
total = 1809
```

نُه پیام رسید (قبل از چاپ مرتبشان کردم چون ترتیب رسیدن می‌تواند فرق کند) و مجموع برابر جمع هر نُه است: ۱۰۰ + ۱۰۱ + ۱۰۲ = ۳۰۳، ۲۰۰ + ۲۰۱ + ۲۰۲ = ۶۰۳، ۳۰۰ + ۳۰۱ + ۳۰۲ = ۹۰۳، و ۳۰۳ + ۶۰۳ + ۹۰۳ = ۱۸۰۹.

در آن مصرف‌کننده یک نکته هست: guard قفل را از روی یک `.await` (یک `yield_now` که به task‌های دیگر نوبت می‌دهد) عبور می‌دهد. با mutex ناهم‌گام Tokio این مجاز است. با `std::sync::Mutex` کتابخانه‌ی استاندارد همان کد کامپایل نمی‌شود:

```rust
let mut g = d.lock().unwrap(); // std MutexGuard
*g += 1;
tokio::task::yield_now().await; // guard هنوز از روی await زنده است
```

```text
error: future cannot be sent between threads safely
   --> src/bin/std_guard.rs:7:13
    |
  7 |       let h = tokio::spawn(async move {
    |  _____________^
  8 | |         let mut g = d.lock().unwrap(); // std MutexGuard
  9 | |         *g += 1;
 10 | |         tokio::task::yield_now().await; // guard still alive across await
 11 | |     });
    | |______^ future created by async block is not `Send`
    |
    = help: within `{async block@src/bin/std_guard.rs:7:26: 7:36}`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  --> src/bin/std_guard.rs:10:34
   |
 8 |         let mut g = d.lock().unwrap(); // std MutexGuard
   |             ----- has type `std::sync::MutexGuard<'_, i32>` which is not `Send`
...
10 |         tokio::task::yield_now().await; // guard still alive across await
   |                                  ^^^^^ await occurs here, with `mut g` maybe used later
```

(آخرین `note:` را بریدم، چون به سورس دانلودشده‌ی Tokio روی ماشین من اشاره می‌کند؛ می‌گفت `tokio::spawn` شرط `Future + Send + 'static` را می‌خواهد.) این همان قاعده‌ی `Send` در مقاله‌ی thread‌هاست. یک task می‌تواند در `.await` مکث کند و بعداً روی thread دیگری ادامه پیدا کند، پس هرچه task از روی `.await` زنده نگه می‌دارد باید `Send` باشد. `MutexGuard` استاندارد `Send` نیست، پس کامپایلر برنامه را رد می‌کند و به همان `.await` که guard هنوز زنده است اشاره می‌کند. اگر هرگز قفل را از روی `.await` نگه ندارید، mutex استاندارد اشکالی ندارد و ارزان‌تر است.

## runtime را مسدود نکنید

این مهم‌ترین اشتباهی است که باید بشناسید. task نباید کاری بکند که thread را مسدود کند (مثل `std::thread::sleep`، یک حلقه‌ی طولانی CPU، یا فراخوانی هم‌گام فایل یا پایگاه داده)، چون تا وقتی thread مسدود است هیچ taskی که با آن شریک است نمی‌تواند اجرا شود. برای نشان دادن واضح، demo از runtime به اسم `current_thread` استفاده می‌کند که در آن فقط یک thread همه‌ی task‌ها را اجرا می‌کند. (به گفته‌ی مستندات Tokio، `#[tokio::main]` به‌طور پیش‌فرض یک runtime چندthreadی می‌سازد؛ با چند thread اثر ملایم‌تر است ولی مشکل همان است.) یک task «ticker» هر ۱۰۰ میلی‌ثانیه یک خط چاپ می‌کند، در حالی که `main` ۵۰۰ میلی‌ثانیه `std::thread::sleep` را صدا می‌زند:

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

(این عددها از اجرای اول‌اند.) در نیمه‌ی اول، خواب مسدودکننده حدود ۵۰۰ میلی‌ثانیه تمام می‌شود و فقط بعد از آن اولین tick در حدود ۶۰۰ میلی‌ثانیه ظاهر می‌شود. ticker تا وقتی تنها thread خواب بود اصلاً نمی‌توانست اجرا شود. حتی انتظار ۱۰۰ میلی‌ثانیه‌ای خودش هم شروع نشد تا وقتی `main` به یک `.await` رسید و thread را رها کرد. در نیمه‌ی دوم همان خواب ۵۰۰ میلی‌ثانیه‌ای به `tokio::task::spawn_blocking` منتقل شده، که آن را روی یک استخر جدا از thread‌ها اجرا می‌کند که برای کار مسدودکننده ساخته شده. حالا tick‌ها سر وقت می‌آیند (حدود ۱۰۰ و ۲۰۰ و ۳۰۰ میلی‌ثانیه) و نتیجه‌ی کار مسدودکننده، `42`، حدود ۵۰۰ میلی‌ثانیه می‌رسد.

## مقایسه با goroutine در Go

فقط چیزهایی که از آن‌ها مطمئنم. scheduler در Go جزو runtime زبان است، پس `go f()` همین‌طوری کار می‌کند؛ در Rust، async به یک crate از نوع runtime مثل Tokio نیاز دارد. تابع‌های async «رنگی» هستند: یک `async fn` را فقط از کد async می‌شود await کرد، پس این انتخاب در گراف فراخوانی‌های شما پخش می‌شود. یک تابع Go را می‌شود از goroutine صدا زد یا نزد، بی‌آنکه امضایش تغییر کند.

## جاهایی که async می‌شکند

- **فراموش‌کردن `.await`** فقط با یک هشدار کامپایل می‌شود و کار بی‌صدا هرگز انجام نمی‌شود. هشدارها را بخوانید.
- **لغو در نقطه‌های `.await` رخ می‌دهد.** futureی که drop شود همان‌جا که هست می‌ایستد، پس پاک‌سازی جایش `Drop` است، نه دستورهای بعد از await.
- **`MutexGuard` استاندارد که از روی `.await` نگه داشته شود** future را `Send` نمی‌گذارد و `tokio::spawn` آن را رد می‌کند. از mutex Tokio استفاده کنید، یا قفل را پیش از `.await` رها کنید.
- **هرگز کد مسدودکننده را مستقیم در یک task اجرا نکنید.** `thread::sleep`، کار سنگین CPU و درایورهای هم‌گام فایل یا پایگاه داده را از `spawn_blocking` بگذرانید.
- **`join!` هم‌زمانی داخل یک task است.** وقتی می‌خواهید thread‌های دیگر هم کمک کنند از `spawn` استفاده کنید.

## تمرین

۱. `async fn fetch(id: u32) -> u32` را بنویسید که ۱۰۰ میلی‌ثانیه می‌خوابد، بعد ده‌تا از آن را با `spawn` اجرا کنید و نتیجه‌ها را از طریق `JoinHandle`‌هایشان جمع کنید.
۲. یکی از آن‌ها را در `tokio::time::timeout` با ۵۰ میلی‌ثانیه بپیچید و خطا را چاپ کنید.
۳. یک حلقه‌ی CPU را روی runtime از نوع `current_thread` کنار یک ticker اجرا کنید، بعد آن را به `spawn_blocking` ببرید.

## قدم بعدی

سرویس‌هایی که حالا می‌توانیم بسازیم باید داده رد و بدل کنند. مقاله‌ی بعد، «Serde و JSON در Rust»، سریالایز و دیسریالایز کردن struct‌ها را می‌گوید، همان‌طور که در Go با `encoding/json` انجام دادیم.
