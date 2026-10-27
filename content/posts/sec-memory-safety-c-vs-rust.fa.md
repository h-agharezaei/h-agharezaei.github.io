+++
date = '2027-05-22T10:00:00+03:30'
draft = false
title = 'امنیت حافظه: C در برابر Rust'
description = 'امنیت حافظه در C، Go و Rust: خارج از محدوده، use-after-free، double free، سرریز و data race، با خروجی واقعی sanitizer و کامپایلر.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "memory-safety", "c", "rust", "sanitizers"]
cover = { image = "/images/covers/sec-memory-safety-c-vs-rust.fa.png", alt = "امنیت حافظه: C در برابر Rust", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [اشتباه‌های رایج رمزنگاری](/fa/posts/sec-crypto-mistakes/)، درباره‌ی ابزارهای سالمی بود که غلط به کار می‌روند. این مقاله یک لایه پایین‌تر است: کدی که حافظه‌ای را می‌خواند یا می‌نویسد که مال آن نیست. {{< term "memory-safety" "امنیت حافظه" >}} یعنی این اتفاق نمی‌افتد. پایه‌های سمت Rust در [Ownership در Rust](/fa/posts/rust-ownership/)، [قرض‌گیری و ارجاع در Rust](/fa/posts/rust-borrowing-references/) و [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) آمده و سمت Go در [اشاره‌گرها و مدل حافظه در Go](/fa/posts/go-pointers-memory/).

> فقط دفاعی. برنامه‌های کوچک خودم هستند که هر کدام عمداً یک نوع باگ را نشان می‌دهند؛ روی macOS arm64 با Apple clang 21، rustc 1.90 و Go 1.26 اجرا شدند. بدون payload و بدون بهره‌برداری. کد دمو محلی است.

## C: باگ‌ها

چهار فایل، هرکدام با یک اشتباه. اول نوشتن ۱۰ بایت در `char buf[8]`:

```c
char buf[8];
memset(buf, 'A', n);   /* n == 10 */
```

`cc -Wall -Wextra` فقط هشدار پارامتر بی‌استفاده داد و درباره‌ی سرریز چیزی نگفت. build معمولی با کد خروج ۱۳۳ و بدون هیچ پیامی متوقف شد (حدسم یک بررسی fortified در `memset` است، ولی راستی‌آزمایی نکردم). با `-fsanitize=address`:

```
ERROR: AddressSanitizer: stack-buffer-overflow on address 0x00016f325da8 ...
WRITE of size 10 at 0x00016f325da8 thread T0
    #1 ... in main oob.c:6
```

یک {{< term "buffer-overflow" "سرریز بافر" >}} با شماره‌ی خط گرفته شد. حالا {{< term "use-after-free" "use-after-free" >}}: `free(p); printf("%d", p[0]);`. build معمولی `4` چاپ کرد، نه ۴۲ که ذخیره کرده بودم، با کد خروج ۰: داده‌ی غلط بدون crash. کامپایلر هم هشداری نداد. {{< term "addresssanitizer" "AddressSanitizer" >}}:

```
ERROR: AddressSanitizer: heap-use-after-free on address 0x602000000970 ...
READ of size 4 at 0x602000000970 thread T0
    #0 ... in main uaf.c:7
```

double free (`free(p); free(p);`) در build معمولی با کد ۱۳۳ و بدون متن متوقف شد؛ ASan نوشت `attempting double-free`. آخرین مورد {{< term "integer-overflow" "سرریز عدد صحیح" >}}: `count * 4` با `count` برابر 2^30. build معمولی `bytes=0` چاپ کرد، همان اندازه‌ی خیلی کوچکی که بعداً به allocation می‌رسد. با `-fsanitize=undefined`:

```
intov.c:6:23: runtime error: signed integer overflow: 1073741824 * 4 cannot be represented in type 'int'
```

راه‌حل مورد اول: `n` را به `sizeof buf` محدود کنید. فایل اصلاح‌شده با `-Wall -Wextra -fsanitize=address,undefined` تمیز اجرا شد و `A` چاپ کرد. فقط آنچه اجرا کردم را می‌گویم؛ پرچم‌های سخت‌سازی مثل `-D_FORTIFY_SOURCE` و stack protector وجود دارند ولی اینجا تستشان نکردم.

## Rust: همان اشتباه‌ها

اندیس `v[10]` روی بردار سه‌عضوی:

```
None
thread 'main' panicked at oob.rs:5:21:
index out of bounds: the len is 3 but the index is 10
```

`v.get(10)` مقدار `None` داد و اندیس‌گذاری panic کرد. panic توقف تمیز است، نه خواندن بی‌صدا. ارجاع معلق اصلاً کامپایل نمی‌شود:

```
error[E0597]: `x` does not live long enough
5 |         r = &x;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `x` dropped here while still borrowed
```

drop کردن مقدار در حال قرض‌گرفته‌شدن `error[E0505]: cannot move out of `s` because it is borrowed` می‌دهد. فرستادن `Rc` به thread دیگر:

```
error[E0277]: `Rc<i32>` cannot be sent between threads safely
```

سرریز به نوع build بستگی دارد. `250 + 5 + 1` در `u8`: با `-C opt-level=0` پیام `attempt to add with overflow` و panic، با `-O` مقدار `0` (wrap). پس build ریلیز بدون درخواست شما بررسی نمی‌کند. با `checked_add` یا `wrapping_add` منظورتان را صریح کنید.

## Go در میانه

Go در زمان اجرا bounds را چک می‌کند: `panic: runtime error: index out of range [10] with length 3`. race را جلو نمی‌گیرد، ولی `go run -race` روی شمارنده‌ی مشترک آن را پیدا کرد: `WARNING: DATA RACE` با goroutine خواننده و نویسنده‌ی قبلی. [الگوهای همزمانی](/fa/posts/go-concurrency-patterns/) را ببینید.

| نوع باگ | C | Go | Rust (safe) |
|---|---|---|---|
| خارج از محدوده | بی‌صدا یا abort | panic | panic یا `get()` |
| Use-after-free | داده‌ی غلط، بدون crash | ممکن نیست | خطای کامپایل E0505/E0597 |
| Double free | abort بدون پیام | ممکن نیست | ممکن نیست |
| سرریز عدد | UB، با UBSan پیدا شد | wrap | panic (debug)، wrap (release) |
| Data race | بررسی نمی‌شود | `-race` پیدا می‌کند | خطای کامپایل E0277 |

## مرز unsafe

بلوک `unsafe` در Rust جایی را نشان می‌دهد که کامپایلر بررسی را کنار می‌گذارد، پس بازبین می‌داند کجا را ببیند. Miri و `cargo geiger` را اجرا نکردم و فقط به‌عنوان ابزار بررسی یا شمارش کد unsafe نامشان را می‌آورم. چیزهای دیگری که اجرا نکردم: سخت‌افزار CHERI، Fil-C و sanitizer در CI. آمار صنعتی را هم راستی‌آزمایی نکردم، پس عددی نقل نمی‌کنم.

## چند نکته‌ی مهم

- هشدارها هیچ‌کدام از این چهار مورد را نگرفتند؛ sanitizerها همه را گرفتند.
- جواب غلط بی‌صدا (`4`) بدتر از crash است.
- build ریلیز در Rust پیش‌فرض روی سرریز wrap می‌کند.
- `unsafe` قولی است که شما می‌دهید، نه کلیدی برای سریع‌تر شدن.

## تمرین

یک تابع C بنویسید که رشته‌ای را در بافر کوچک کپی کند، آن را خراب کنید و با ASan پیدا کنید. بعد به Rust ببریدش و ببینید چه خطایی می‌گیرید.

## قدم بعدی

مقاله‌ی بعدی: fuzzing برای پیدا کردن باگ امنیتی.
