+++
date = '2027-02-26T10:00:00+03:30'
draft = false
title = 'Future، Pin و درون async در Rust'
description = 'async fn در Rust واقعاً چیست: trait به نام Future، waker، block_on و join دست‌نویس، اندازه‌ی state machine، دلیل وجود Pin و لغو کار با drop.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "async", "pin", "future", "advanced"]
cover = { image = "/images/covers/rust-pin-future-internals.fa.png", alt = "Future، Pin و درون async در Rust", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/rust-performance-criterion/) درباره‌ی اندازه‌گیری بود. این مقاله جعبه‌ی زیر [async/await و Tokio](/fa/posts/rust-async-tokio/) را باز می‌کند: future دقیقاً چیست، چه کسی آن را صدا می‌زند و چرا `Pin` در همه‌ی signatureها دیده می‌شود. قطعه‌ها را فقط با کتاب‌خانه‌ی استاندارد خودمان می‌سازیم و در انتها همان کد را زیر Tokio اجرا می‌کنیم.

> همه‌ی کدها با Rust نسخه‌ی 1.90 و edition 2024 کامپایل و اجرا شده‌اند. خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## trait به نام Future

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}
```

`poll` یا `Poll::Ready(value)` برمی‌گرداند یا `Poll::Pending`. یک future تا وقتی کسی `poll` نکند هیچ کاری نمی‌کند. اگر `Pending` برگرداند، باید ترتیبی بدهد که وقتی پیشرفت ممکن شد، **waker** داخل `cx` صدا زده شود. این future را خودم با دست نوشته‌ام: N بار `Pending` می‌گوید و هر بار خودش را بیدار می‌کند.

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

برای poll کردن دستی به یک `Waker` نیاز دارم. پیاده‌سازی `std::task::Wake` برای نوعی داخل `Arc` یکی می‌دهد. این یکی فقط بیدارشدن‌ها را می‌شمارد:

```rust
pub struct CountingWaker(pub AtomicUsize);
impl Wake for CountingWaker {
    fn wake(self: Arc<Self>) { self.0.fetch_add(1, Ordering::SeqCst); }
}
// waker = Waker::from(Arc::new(CountingWaker(..))); cx = Context::from_waker(&waker)
// loop { fut.as_mut().poll(&mut cx) } with Pin::new(&mut fut)
```

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

اگر به بیدارشدن‌ها کاری ندارید، `Waker::noop()` در Rust 1.90 در دسترس است.

## یک executor کوچک و join

**Executor** حلقه‌ای است که future را poll می‌کند و تا وقتی waker صدا زده نشده می‌خوابد. مال من thread را park می‌کند و waker آن را unpark می‌کند:

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

`join2(a, b)` futureای است که دو future را در اختیار دارد، در هر `poll` هر دو را poll می‌کند و نتیجه‌ی هر کدام را تا تمام شدن هر دو نگه می‌دارد (حدود ۲۵ خط؛ هر دو future را در `Pin<Box<_>>` نگه می‌دارد). دو countdown را اجرا کردم، A با ۳ دور pending و B با ۱ دور:

```text
  A: pending, 2 left
  B: pending, 0 left
  A: pending, 1 left
  A: pending, 0 left
joined = ("A", "B")
```

یک thread، دو task، به‌صورت درهم. `tokio::join!` از نظر مفهومی همین است.

## async fn یک state machine است

کامپایلر هر بلوک `async` را به یک نوع بی‌نام تبدیل می‌کند که `Future` را پیاده می‌کند: یک enum با یک variant برای هر `.await` که متغیرهای محلیِ زنده در طول آن را نگه می‌دارد. `size_of_val` این را نشان می‌دهد (debug و release اعداد یکسان دادند):

```text
no await        : 1
one await       : 2
8 bytes kept    : 10
1024 bytes kept : 1026
1024 dead early : 2
nested 2x1024   : 1027
```

اندازه‌ی future برابر چیزی است که باید از یک `.await` عبور کند: یک `[u8; 1024]` که از `.await` رد شود حدود ۱ کیلوبایت هزینه دارد، ولی همان آرایه اگر در یک بلوک داخلی قبل از `.await` از بین برود هزینه‌ای ندارد. ۱ یا ۲ بایت اضافه همان برچسب state است. اعداد دقیق را جزئیات کامپایلر همین نسخه بدانید؛ درس این است که نگه‌داشتن مقدارهای بزرگ در طول await، future را بزرگ می‌کند و برای همین گاهی صدا زدن‌های async تودرتو را `Box::pin` می‌کنند.

## چرا Pin وجود دارد

داخل آن state machine یک متغیر محلی می‌تواند به متغیر محلی دیگر اشاره کند، پس future ممکن است pointerای به خودش داشته باشد. move کردن چنین مقداری pointer را خراب می‌کند. یک demo با raw pointer (pointer کهنه را هرگز dereference نمی‌کنم):

```text
before move: &value = 0x16b9917f8, stored ptr = 0x16b9917f8, same = true
after move : &value = 0x16b991808, stored ptr = 0x16b9917f8, same = false
```

فیلد جابه‌جا شد ولی آدرس ذخیره‌شده نه. `Pin<&mut T>` یعنی قول می‌دهیم این مقدار تا وقتی drop نشده دیگر move نشود. بیشتر نوع‌ها اهمیتی نمی‌دهند و trait خودکار **Unpin** را دارند که pin کردن را بی‌اثر می‌کند: `u32`، `String` و `CountdownFuture` من همه از بررسی `is_unpin` رد شدند، پس `Pin::new(&mut fut)` برایشان کار می‌کند. بلوک‌های async از نوع `!Unpin` هستند. poll مستقیم آن‌ها کامپایل نمی‌شود:

```text
error[E0599]: no method named `poll` found for `async` block ...
help: consider pinning the expression
   let mut pinned = std::pin::pin!(fut);
```

و `Pin::new(&mut fut)` این خطا را می‌دهد: ``the trait `Unpin` is not implemented for `{async block ...}` `` با یادداشتی که `pin!` یا `Box::pin` را پیشنهاد می‌کند. دو راه pin کردن: `Box::pin(fut)` آن را روی heap می‌گذارد (ببینید [smart pointerها](/fa/posts/rust-smart-pointers/)) و `std::pin::pin!(fut)` آن را روی stack pin می‌کند. هر دو درست poll می‌شوند:

```text
Box::pin   -> Ready(1)
pin!       -> Ready(1)
```

## لغو یعنی drop

future فقط یک مقدار است، پس drop کردنش آن را لغو می‌کند. یک guard که داخل بلوک async ساخته شده، با drop شدن future از بین می‌رود، حتی اگر بلوک هیچ‌وقت تمام نشده باشد:

```text
  slow: pending, 4 left
polled once, now dropping the future
  drop guard inside async
after scope
```

متن "never printed" هیچ‌وقت چاپ نشد. این همان ایده‌ی guard از نوع `Drop` در `select!` در Tokio است: پاک‌سازی جایش در `Drop` است.

## همان کد زیر Tokio

`CountdownFuture` من بدون تغییر زیر `tokio::runtime::Builder::new_current_thread().build()?.block_on(...)` اجرا می‌شود و خروجی‌اش با executor خودم یکی است (`start`، دو pending، `got a` و `result = 42`). Tokio تایمر، IO و زمان‌بندی چندthread اضافه می‌کند، ولی قرارداد همان `poll` و `Waker` است.

## چند نکته برای دقت

- برگرداندن `Pending` بدون ترتیب دادن یک بیدارسازی یعنی task برای همیشه می‌خوابد.
- بعد از `Ready` دیگر future را poll نکنید؛ بلوک‌های `async` با پیام "resumed after completion" panic می‌کنند.
- متغیرهای محلی بزرگ در طول `.await` futureها را بزرگ می‌کنند.
- move کردن مقدار `!Unpin` پین‌شده در کد safe ممکن نیست؛ برای دور زدنش سراغ `unsafe` نروید.

## تمرین

تابع `yield_now()` را بنویسید: futureای که بار اول `Pending` برمی‌گرداند (با `wake_by_ref`) و بار دوم `Ready(())`. دو بلوک async را که با آن حلقه می‌زنند زیر `join2` اجرا کنید.

## قدم بعدی

مقاله‌ی بعد observability در Rust با `tracing` است: لاگ ساخت‌یافته و span برای کد async.
