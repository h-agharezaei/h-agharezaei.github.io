+++
date = '2027-03-14T10:00:00+03:30'
draft = false
title = 'Rust و WebAssembly'
description = 'Rust و WebAssembly: کامپایل به wasm32-unknown-unknown و wasm32-wasip1، رد کردن رشته از مرز wasm به‌صورت دستی و با wasm-bindgen، و کاربردهای wasm.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "wasm", "webassembly", "wasi", "wasm-bindgen", "intermediate"]
cover = { image = "/images/covers/rust-wasm.fa.png", alt = "Rust و WebAssembly", hiddenInSingle = true }
+++

موضوع [مقاله‌ی قبل](/fa/posts/rust-docker-ci-release/) release engineering بود. این مقاله درباره‌ی نوع دیگری از خروجی است: فایل `.wasm`. در [مقاله‌ی unsafe و FFI](/fa/posts/rust-unsafe-ffi/) با **C ABI** از یک مرز رد شدیم و Go هم در [فراخوانی Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) همین کار را کرد. WebAssembly راه دیگری برای رد شدن از مرز است، با یک sandbox در وسط.

**WebAssembly** (به‌اختصار wasm) یک قالب دودویی قابل‌حمل برای دستورهاست که روی یک ماشین مجازی ایزوله اجرا می‌شود. یک ماژول wasm خودش به DOM، فایل یا شبکه دسترسی ندارد؛ فقط **linear memory** خودش را دارد و هر تابعی که میزبان (مرورگر، Node یا یک runtime) به آن بدهد. از مرز فقط عدد رد می‌شود.

> همه‌چیز با Rust 1.90، edition 2024، Node 20.13 و `wasm-bindgen` نسخه‌ی 0.2.129 روی macOS ساخته و اجرا شد. مرورگر در دسترس نبود، پس همه‌چیز از Node بارگذاری شد و درباره‌ی مرورگر ادعایی ندارم. دموها crateهای محلی‌اند: `raw`، `bindgen`، `wasi` و `gohello`.

## ساده‌ترین مسیر: فقط عدد

یک بار targetها را اضافه کنید: `rustup target add wasm32-unknown-unknown wasm32-wasip1`. نوع crate باید `cdylib` باشد و تابع‌ها دقیقاً مثل مقاله‌ی FFI هستند:

```rust
#[unsafe(no_mangle)]
pub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }

#[unsafe(no_mangle)]
pub extern "C" fn fib(n: u32) -> u64 {
    let (mut a, mut b) = (0u64, 1u64);
    for _ in 0..n { (a, b) = (b, a + b); }
    a
}
```

یک profile به اسم `small` هم اضافه کردم (`opt-level = "z"`، `lto = true`، `strip = true` و `codegen-units = 1`) و crate را دو بار با `cargo build --release --target wasm32-unknown-unknown` و `--profile small` ساختم:

```text
-rwxr-xr-x  1 hossein  staff  24161 raw.wasm   (release)
-rwxr-xr-x  1 hossein  staff  10334 raw.wasm   (small)
```

این اندازه‌ها شامل تابع‌های رشته‌ای پایین هم هستند.

## رشته به linear memory نیاز دارد

رشته عدد نیست؛ پس میزبان باید بایت‌هایش را داخل حافظه‌ی ماژول بگذارد و یک pointer و یک طول بدهد. ماژول برای این کار `alloc` و `dealloc` (با `Layout` و alignment برابر ۱) export می‌کند، و تابعی که بایت‌ها را می‌خواند:

```rust
#[unsafe(no_mangle)]
pub unsafe extern "C" fn count_chars(ptr: *const u8, len: usize) -> usize {
    let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
    std::str::from_utf8(bytes).map(|s| s.chars().count()).unwrap_or(0)
}
```

سمت JavaScript، با `node js/run.mjs <file>`:

```js
const { instance } = await WebAssembly.instantiate(bytes, {});
const { add, fib, alloc, dealloc, count_chars, memory } = instance.exports;
console.log("add(2, 40) =", add(2, 40));
console.log("fib(90) =", fib(90));

const enc = new TextEncoder().encode("سلام wasm");
const ptr = alloc(enc.length);
new Uint8Array(memory.buffer, ptr, enc.length).set(enc);
console.log(`bytes=${enc.length} chars=${count_chars(ptr, enc.length)}`);
dealloc(ptr, enc.length);
```

```text
add(2, 40) = 42
fib(90) = 2880067194370816120n
bytes=13 chars=9
```

خروجی هر دو build یکی بود. به `n` دقت کنید: `u64` در Rust در JavaScript به‌شکل `BigInt` می‌رسد. انضباطش مثل C FFI است: تخصیص حافظه با شماست، pointer فقط یک عدد است و هیچ‌چیز شما را چک نمی‌کند.

## wasm-bindgen: glue تولیدشده

نوشتن این‌ها با دست برای هر تابع جواب نمی‌دهد. crate و CLI به اسم **wasm-bindgen** این glue را تولید می‌کنند:

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}! Greetings from Rust.")
}
```

نسخه‌ی CLI باید دقیقاً با نسخه‌ی crate یکی باشد (اینجا هر دو 0.2.129). بعد از `wasm-bindgen target/wasm32-unknown-unknown/release/greeter.wasm --target nodejs --out-dir pkg` یک فایل `.js`، یک `.d.ts` و یک `_bg.wasm` می‌گیریم:

```text
$ node run.cjs
Hello, Roham! Greetings from Rust.
Hello, سلام! Greetings from Rust.
```

اندازه: خروجی cargo (با `opt-level = "z"`، `lto` و `strip`) برابر 27347 بایت بود، `greeter_bg.wasm` بعد از پردازش 12716 بایت است، به‌علاوه‌ی 3769 بایت JavaScript تولیدشده. با نسخه‌ی دستی و همین تابع‌ها مقایسه نکردم، پس درباره‌ی هزینه‌ی glue ادعایی ندارم.

## WASI: wasm بیرون از مرورگر

**WASI** یک رابط سیستمی (فایل، آرگومان، stdin، ساعت) است که میزبان صریحاً می‌دهد. یک CLI ساده‌ی Rust تغییر کدی نمی‌خواهد، فقط target: `cargo build --release --target wasm32-wasip1` فایل `wordcount.wasm` با 71215 بایت داد. `node:wasi` در Node (آزمایشی است و هشدار چاپ می‌کند) آن را اجرا کرد:

```text
$ printf 'one two\nthree\n' | node run.mjs target/wasm32-wasip1/release/wordcount.wasm
args=["a", "b"] lines=2 words=3
file says: hello from the host
```

برنامه `/data/hello.txt` را می‌خواند. این مسیر فقط وجود دارد چون میزبان `preopens: { "/data": ... }` داده است. با `preopens: {}` همان ماژول فقط خط اول را چاپ کرد: فایل دیده نمی‌شد. این همان sandbox است.

## Go در همین زمین

Go هم به wasm کامپایل می‌شود: `GOOS=js GOARCH=wasm` و `GOOS=wasip1 GOARCH=wasm`. یک hello world زیر Node WASI عبارت `hello from Go` را چاپ کرد و اندازه‌ها 2635407 بایت (js) و 2607556 بایت (wasip1؛ با `-ldflags="-s -w"` برابر 2557546) بود. hello world معادل در Rust با `opt-level=z`، `lto` و `strip=symbols` برابر 42565 بایت شد. برنامه‌ی Go runtime خودش را همراه دارد که محتمل‌ترین دلیل است، ولی نسنجیدم کدام بخش سهم بیشتری دارد.

## wasm کجا به کار می‌آید

- افزونه‌ها و کد غیرقابل‌اعتماد: میزبان تعیین می‌کند ماژول به چه دست بزند.
- به‌اشتراک‌گذاری یک تکه منطق با JavaScript (اعتبارسنجی، parse، codec).
- runtimeهای edge یا serverless که ماژول wasm می‌پذیرند.

و کجا نه:

- یک سرویس backend معمولی: باینری native ساده‌تر است و پشتیبانی WASI در کتاب‌خانه‌ها (socket، thread) یکدست نیست.
- کار سنگین با DOM: wasm برای آن هم از JavaScript رد می‌شود.
- فراخوانی‌های کوچک و پرتکرار با رشته: هر فراخوانی بایت‌ها را از مرز کپی می‌کند.

## چند نکته که باید حواستان باشد

- نسخه‌ی CLI و crate مربوط به `wasm-bindgen` باید یکی باشند.
- بدون glue فقط عدد رد می‌شود؛ `u64` در JavaScript به `BigInt` تبدیل می‌شود.
- هر چه `alloc` کردید آزاد کنید، وگرنه ماژول نشت می‌کند.
- WASI در Node آزمایشی است و ممکن است تغییر کند.
- اندازه به profile بستگی دارد (24161 در برابر 10334 بایت بالا)؛ build خودتان را اندازه بگیرید.

## تمرین

تابع `reverse(ptr, len)` را export کنید که رشته را درجا برعکس کند و از Node صدایش بزنید. بعد ببینید `wasm-bindgen` چقدر کد کم می‌کند.

## قدم بعدی

مقاله‌ی بعد پروژه‌ی پایانی Rust است: یک سرویس کامل.
