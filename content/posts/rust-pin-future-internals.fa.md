+++
date = '2027-02-26T10:00:00+03:30'
draft = false
title = 'Future، Pin و درون async در Rust'
description = 'async fn در Rust واقعاً چیست: trait به نام Future، waker، block_on و join دست‌نویس، اندازه‌ی state machine، دلیل وجود Pin و لغو کار با drop.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "pin", "future", "advanced"]
cover = { image = "/images/covers/rust-pin-future-internals.fa.png", alt = "Future، Pin و درون async در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی async و Tokio](/fa/posts/rust-async-tokio/) دیدیم که صدا زدن یک `async fn` بدنه‌اش را اجرا نمی‌کند و فقط یک {{< term "rust-future" "future" >}} برمی‌گرداند که تا کسی منتظرش نشود کاری نمی‌کند. همان‌جا فقط گفتیم که runtime پشت صحنه با متدی به اسم `poll` از future می‌پرسد «تمام شدی؟»، و قول دادیم بعداً دقیق‌تر ببینیم. این مقاله همان بعداً است. دو سؤال داریم. اولی: «کسی منتظرش بشود» دقیقاً یعنی چه؟ چه چیزی future را راه می‌اندازد و چه چیزی می‌فهمد کارش تمام شده؟ دومی: چرا هر جا با future سروکار داریم یک {{< term "rust-pin" "Pin" >}} در signature دیده می‌شود، و چرا این‌قدر ترسناک به نظر می‌رسد؟

این مقاله هر دو سؤال را با ساختن خود چیزها جواب می‌دهد، بعد از [اندازه‌گیری با Criterion](/fa/posts/rust-performance-criterion/). یک future ساده را دست‌نویس می‌سازیم، یک {{< term "rust-executor" "executor" >}} کوچک می‌نویسیم که آن را اجرا کند، ببینیم یک `async fn` از درون چه شکلی است، و بعد با یک تصویر ساده می‌فهمیم `Pin` برای چه لازم شده. همه‌ی قطعه‌ها فقط با کتاب‌خانه‌ی استاندارد ساخته می‌شوند و در انتها همان کد را زیر Tokio اجرا می‌کنیم.

> همه‌ی کدها را با Rust 1.90 (`rustc 1.90.0`) و edition 2024 دوباره کامپایل و اجرا کرده‌ام. برنامه‌ها فقط از کتاب‌خانه‌ی استاندارد استفاده می‌کنند، به‌جز مقایسه‌ی آخر که `tokio` نسخه‌ی 1.54.1 (قابلیت `rt`، طبق `Cargo.lock`) را دارد. خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند. چند مثال کوچک (async fn با reference به متغیر خودش، `swap` روی future پین‌شده، جابه‌جا کردن `Pin<Box<_>>` و poll بعد از پایان) را فقط برای نمایش در برنامه‌های جدا نوشتم و اجرا کردم. آدرس‌های حافظه از اجرایی به اجرای دیگر فرق می‌کنند. از پیام‌های خطا خط‌های `note:` و «For more information…» را حذف کرده‌ام.

## trait به نام Future

بیایید از خود قرارداد شروع کنیم. این همه‌ی چیزی است که یک future باید داشته باشد:

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}
```

یک متد دارد: `poll`. کسی که future را اجرا می‌کند، به آن می‌گوید «کارت را جلو ببر، تمام شده‌ای؟». future دو جواب می‌تواند بدهد: `Poll::Ready(value)` یعنی «تمام شد و نتیجه این است»، یا `Poll::Pending` یعنی «هنوز نه».

مثل بچه‌ای که در ماشین مدام می‌پرسد «رسیدیم؟». اگر هر ثانیه بپرسد، همه را خسته می‌کند. پس در Rust قراردادی هست: اگر future بگوید `Pending`، باید ترتیبی بدهد که وقتی پیشرفت ممکن شد، خودش خبر بدهد. ابزار این خبر دادن {{< term "rust-waker" "waker" >}} است که داخل `cx` (از نوع `Context`) قرار دارد. waker مثل زنگی است که future می‌تواند به صدا دربیاورد، و کسی که future را اجرا می‌کند (executor) تا آن زنگ نخورد سراغش نمی‌آید.

دو تکه‌ی دیگر را هم بعداً توضیح می‌دهم: `Pin<&mut Self>` به جای `&mut self` معمولی چرا آمده (بخش «چرا Pin وجود دارد»)، و `Context<'_>` فقط جعبه‌ای است که waker در آن است.

### یک future دست‌نویس

سه پرسش پشت‌سرهم: چند بار `Pending` بگوید؟ چه چیزی چاپ کند؟ چه زمانی waker را بزند؟ این future را من نوشته‌ام که N بار `Pending` می‌گوید و هر بار خودش را بیدار می‌کند:

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

هر بار که `poll` صدا زده شود: اگر `remaining` صفر است، نتیجه را آماده اعلام می‌کند (نام future). وگرنه یکی از `remaining` کم می‌کند، یک خط چاپ می‌کند، `wake_by_ref()` را صدا می‌زند، یعنی «زنگ را بزن، دوباره بیا سراغم»، و `Pending` برمی‌گرداند.

برای poll کردن دستی به یک `Waker` احتیاج داریم. اگر نوعی `std::task::Wake` را پیاده کند و داخل یک `Arc` باشد، می‌شود از آن waker ساخت. این یکی فقط می‌شمارد چند بار زنگ خورده:

```rust
pub struct CountingWaker(pub AtomicUsize);
impl Wake for CountingWaker {
    fn wake(self: Arc<Self>) { self.0.fetch_add(1, Ordering::SeqCst); }
}
// waker = Waker::from(Arc::new(CountingWaker(..))); cx = Context::from_waker(&waker)
// loop { fut.as_mut().poll(&mut cx) } with Pin::new(&mut fut)
```

برنامه‌ی `manual_poll` یک `CountdownFuture` با ۳ شمارش می‌سازد و در حلقه آن را poll می‌کند، تا `Ready`. خروجی:

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

سه poll اول `Pending` دادند و هرکدام یک خط از داخل future چاپ کردند و waker را زدند. poll چهارم دید `remaining` صفر است و `Ready("countdown")` برگرداند. `wake count = 3` یعنی waker سه بار زنگ خورد، دقیقاً به تعداد `Pending`ها. (داخل همین مثال دستی، `Pin::new(&mut fut)` کار می‌کند چون `CountdownFuture` از نوع `Unpin` است. معنی‌اش در بخش Pin می‌آید.)

اگر به بیدارشدن‌ها کاری ندارید، `Waker::noop()` در Rust 1.90 در دسترس است: wakerی که کاری نمی‌کند. همین برنامه با آن دو خط دیگر هم چاپ می‌کند: `noop: Pending` و بعد `noop: Ready("noop")` (به‌علاوه‌ی خط داخلی خود future، `noop: pending, 0 left`، قبل از اولی).

## یک executor کوچک

حالا چه کسی future را poll می‌کند و چه کسی به زنگ waker جواب می‌دهد؟ **Executor**. ساده‌ترین نمونه‌اش حلقه‌ای است که future را poll می‌کند، اگر `Pending` بود می‌خوابد، و وقتی waker زنگ زد از خواب بلند می‌شود و دوباره poll می‌کند. مال من thread را `park` می‌کند (می‌خواباند) و waker آن را `unpark` می‌کند:

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

خط به خط: `pin!` آن future را در جایی ثابت نگه می‌دارد (بخش Pin). waker از روی thread فعلی ساخته می‌شود. در حلقه، `poll` صدا زده می‌شود؛ `Ready` یعنی تمام و نتیجه را برگردان، `Pending` یعنی `thread::park()` و بخواب تا waker زنگ بزند. چون `CountdownFuture` خودش را قبل از `Pending` بیدار می‌کند، thread فوراً بیدار می‌شود و ادامه می‌دهد. برنامه‌ی `exec` یک بلوک async را با این executor اجرا می‌کند:

```text
start
  a: pending, 1 left
  a: pending, 0 left
got a
result = 42
```

بلوک async اول `start` را چاپ می‌کند و بعد `CountdownFuture` را `.await` می‌کند. دو بار `Pending` (دو خط `pending`)، بعد `Ready` شد، `got a` چاپ شد و بلوک `42` برگرداند که `block_on` آن را به ما داد.

### join: دو کار روی یک thread

با همین قطعه‌ها یک `join2` هم می‌شود نوشت: futureای که دو future را نگه می‌دارد، در هر `poll` هر دو را poll می‌کند و نتیجه‌ی هر کدام را تا تمام شدن هر دو نگه می‌دارد (حدود ۲۵ خط؛ هر دو future را در `Pin<Box<_>>` نگه می‌دارد). دو countdown را اجرا کردم، A با ۳ دور pending و B با ۱ دور:

```text
  A: pending, 2 left
  B: pending, 0 left
  A: pending, 1 left
  A: pending, 0 left
joined = ("A", "B")
```

یک thread، دو کار به‌صورت درهم: اولین poll هر دو را جلو برد (خط اول A و دوم B)، B در همان دور بعدی `Ready` شد و A دو دور دیگر لازم داشت. وقتی هر دو تمام شدند، `join2` نتیجه‌ها را به‌صورت یک tuple داد. `tokio::join!` از نظر مفهومی همین است.

## async fn یک state machine است

حالا چیزی که با `async fn` می‌نویسیم، کامپایلر به چه تبدیل می‌کند؟ بلوک `async` نقطه‌هایی دارد که در آن‌ها (در هر `.await`) ممکن است کار متوقف شود و بعداً ادامه پیدا کند. پس future باید یادش بماند «کجا بودم و چه متغیرهایی داشتم». کامپایلر برای هر بلوک async یک نوع بی‌نام می‌سازد که `Future` را پیاده می‌کند: یک enum (یک **state machine**) با یک حالت برای هر `.await`، که متغیرهای محلی زنده در طول آن توقف را نگه می‌دارد.

می‌شود این را اندازه گرفت. `size_of_val` اندازه‌ی خود future را به بایت می‌دهد (در debug و release اعداد یکسان بودند):

```text
no await        : 1
one await       : 2
8 bytes kept    : 10
1024 bytes kept : 1026
1024 dead early : 2
nested 2x1024   : 1027
```

خط‌به‌خط: async fn بدون await فقط ۱ بایت است (برچسب حالت). با یک await ۲ بایت. وقتی یک آرایه‌ی ۸ بایتی از یک `.await` عبور می‌کند، ۱۰ بایت می‌شود، و برای ۱۰۲۴ بایت، ۱۰۲۶. ولی همان آرایه‌ی ۱۰۲۴ بایتی اگر در یک بلوک داخلی قبل از `.await` از بین برود، future فقط ۲ بایت است (`1024 dead early`)، چون هنگام توقف دیگر زنده نیست. و دو فراخوانی تودرتو که هر کدام ۱ کیلوبایت نگه می‌دارند، ۱۰۲۷ بایت شد، نه حدود ۲۰۰۰. دلیلش احتمالاً این است که future داخلی اول وقتی تمام شود دور ریخته می‌شود و future داخلی دوم می‌تواند از همان جا استفاده کند؛ جزئیات چیدمان را بررسی نکردم.

پس اندازه‌ی future برابر چیزی است که باید از یک `.await` عبور کند. اعداد دقیق جزئیات کامپایلر همین نسخه‌اند؛ درس این است که نگه‌داشتن مقدارهای بزرگ در طول await، future را بزرگ می‌کند و برای همین گاهی صدا زدن‌های async تودرتو را `Box::pin` می‌کنند.

## چرا Pin وجود دارد

حالا سؤال دوم. نگاه کنید این async fn چه می‌کند:

```rust
async fn uses_own_local() -> usize {
    let buf = [7u8; 16];
    let r = &buf; // points at a local of this very future
    ready(()).await; // `buf` and `r` must both survive the pause
    r.len()
}
```

`r` یک reference به `buf` است و هر دو از یک `.await` رد می‌شوند. پس هر دو باید داخل future ذخیره شوند، و یعنی یکی از فیلدهای future به فیلد دیگر خودش اشاره می‌کند. (این کد کامپایل می‌شود و با `block_on` خودمان `result = 16` داد؛ future ۳۲ بایت بود.) به چنین ساختاری **self-referential** می‌گویند. تصویرش:

```text
before the move:                     after the move:
+----------------------+             +----------------------+
| value = 7            | <--+        | value = 7            |   (new place)
| ptr   = &value       | ---+        | ptr   = old address  | ---> where value no longer is
+----------------------+             +----------------------+
```

مشکل کجاست؟ move کردن یعنی کپی بایت‌ها در یک جای جدید. `value` به جای جدید رفته، ولی `ptr` همان آدرس قدیمی را نگه داشته است. این یک اشاره‌گر معلق است. نشانش دادن آسان است: یک struct ساده با raw pointer (اشاره‌گر قدیمی را هرگز dereference نمی‌کنم؛ خواندن از آن رفتار تعریف‌نشده است):

```text
before move: &value = 0x16d969488, stored ptr = 0x16d969488, same = true
after move : &value = 0x16d969498, stored ptr = 0x16d969488, same = false
```

(آدرس‌ها از اجرایی به اجرای دیگر عوض می‌شوند.) قبل از move، آدرس `value` و آدرس ذخیره‌شده یکی بودند (`same = true`). بعد از move، `value` در آدرس جدید است ولی `ptr` هنوز آدرس قبلی را دارد (`same = false`). برای یک future که ممکن است بین دو `poll` جابه‌جا شود، این فاجعه است، چون `r` در `r.len()` از آدرس قدیمی می‌خواند.

راه‌حل Rust این است که قول بدهیم future بعد از اولین `poll` دیگر جابه‌جا نمی‌شود. `Pin<&mut T>` همین قول است: «این مقدار تا وقتی drop نشده، حرکت نمی‌کند». به همین دلیل `poll` به‌جای `&mut self` یک `self: Pin<&mut Self>` می‌گیرد.

### Unpin: بیشتر نوع‌ها اهمیت نمی‌دهند

بیشتر نوع‌ها اشاره‌گر به خودشان ندارند و جابه‌جا شدنشان مشکلی ایجاد نمی‌کند. این نوع‌ها خودکار trait به نام **Unpin** دارند، که یعنی «پین کردن من بی‌اثر است». برای آن‌ها `Pin::new(&mut x)` کار می‌کند. `u32`، `String` و `CountdownFuture` خودم همه از یک بررسی ساده‌ی `is_unpin` رد شدند. ولی بلوک‌های async ممکن است self-referential باشند، پس `!Unpin` هستند. اگر بخواهید یکی را مستقیم poll کنید:

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

کامپایلر می‌گوید روی خود `fut` متد `poll` پیدا نمی‌شود: `poll` فقط روی `Pin<&mut Self>` تعریف شده. بخش `help` راه را هم نشان می‌دهد: با `pin!` پینش کنید. راه میان‌بر `Pin::new(&mut fut)` هم کار نمی‌کند:

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

`Pin::new` فقط برای نوع‌های `Unpin` است، چون فقط آن‌ها را می‌شود بی‌خطر پین کرد؛ و بلوک async از آن نوع نیست. پیام یک راه دیگر هم پیشنهاد می‌کند: `Box::pin`.

### دو راه پین کردن

`Box::pin(fut)` future را روی heap می‌گذارد (ببینید [smart pointerها](/fa/posts/rust-smart-pointers/)): حتی اگر خود `Box` جابه‌جا شود، آنچه داخل heap است سر جایش می‌ماند. `std::pin::pin!(fut)` آن را روی stack پین می‌کند و دیگر نمی‌توانید به خود متغیر دست بزنید. هر دو درست poll می‌شوند:

```text
Box::pin   -> Ready(1)
pin!       -> Ready(1)
```

برای دیدن اینکه Box واقعاً future را جابه‌جا نمی‌کند، در یک برنامه‌ی جدا آدرس future را قبل و بعد از جابه‌جا کردن `Pin<Box<_>>` چاپ کردم، و `future stayed at the same address: true` آمد: فقط خود اشاره‌گر حرکت کرد.

و چرا کد امن نمی‌تواند future پین‌شده را جابه‌جا کند؟ چون برای به دست آوردن `&mut T` از `Pin<&mut T>` به `DerefMut` احتیاج دارد، که فقط برای `Unpin` پیاده شده. با دو future پین‌شده و `std::mem::swap` امتحان کردم:

```text
error[E0596]: cannot borrow data in dereference of `Pin<&mut impl Future<Output = ()>>` as mutable
  --> src/bin/x_swap.rs:11:20
   |
11 |     std::mem::swap(&mut *a, &mut *b);
   |                    ^^^^^^^ cannot borrow as mutable
   |
   = help: trait `DerefMut` is required to modify through a dereference, but it is not implemented for `Pin<&mut impl Future<Output = ()>>`
```

کامپایلر اجازه نمی‌دهد `&mut` به future پین‌شده بگیرید، پس نمی‌توانید با `swap` یا `mem::replace` جابه‌جایش کنید. همین جلوی ساختن اشاره‌گر معلق را می‌گیرد.

## لغو یعنی drop

future فقط یک مقدار است، پس drop کردنش آن را لغو می‌کند ({{< term "task-cancellation" "لغو با drop" >}}). در برنامه‌ی `cancel` یک بلوک async داریم که داخلش یک `Guard` (با پیاده‌سازی `Drop` که چیزی چاپ می‌کند) ساخته می‌شود و بعد یک countdown ۵تایی را `.await` می‌کند. فقط یک بار poll می‌کنم و future را drop می‌کنم:

```text
  slow: pending, 4 left
polled once, now dropping the future
  drop guard inside async
after scope
```

اولین poll تا `Pending` اول پیش رفت (خط اول). بعد future drop شد و guard که داخلش زنده بود، هم از بین رفت (`drop guard inside async`)، حتی با اینکه بلوک هیچ‌وقت تمام نشد. خط `never printed` که بعد از await بود، هیچ‌وقت چاپ نشد. همین ایده‌ی پشت `select!` و `timeout` در Tokio است: کاری که برنده نشده، drop می‌شود، پس پاک‌سازی باید در `Drop` باشد، نه در خط‌های بعد از `.await`.

## همان کد زیر Tokio

`CountdownFuture` من را بدون هیچ تغییری زیر `tokio::runtime::Builder::new_current_thread().build()?.block_on(...)` اجرا کردم و خروجی‌اش با executor خودم یکی بود (`start`، دو `pending`، `got a` و `result = 42`). Tokio تایمر، I/O و زمان‌بندی چندthread را اضافه می‌کند، ولی قرارداد همان `poll` و `Waker` است.

## قواعد قرارداد Future

- **برگرداندن `Pending` بدون ترتیب دادن یک بیدارسازی**: future را برای همیشه فراموش می‌کند، چون executor منتظر زنگ می‌ماند. (طبق مستندات `Future`، بعد از `Pending` task فقط وقتی دوباره poll می‌شود که waker بیدار شده باشد.) این را اجرا نکردم.
- **بعد از `Ready` دیگر future را poll نکنید.** برای یک بلوک async این panic است. امتحان کردم: بار اول `Ready(5)` آمد و بار دوم `` `async fn` resumed after completion ``.
- **متغیرهای محلی بزرگ در طول `.await`** future را بزرگ می‌کنند (جدول اندازه‌ها بالا).
- **جابه‌جا کردن مقدار `!Unpin` پین‌شده در کد safe ممکن نیست**؛ برای دور زدنش سراغ `unsafe` نروید.

## تمرین

تابع `yield_now()` را بنویسید: futureای که بار اول `Pending` برمی‌گرداند (با `wake_by_ref`) و بار دوم `Ready(())`. دو بلوک async را که با آن حلقه می‌زنند زیر `join2` اجرا کنید.

## قدم بعدی

«Observability در Rust با tracing»: لاگ ساخت‌یافته و span برای دیدن سرگذشت یک درخواست میان taskهای درهم.
