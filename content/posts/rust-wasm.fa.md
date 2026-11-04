+++
date = '2027-03-14T10:00:00+03:30'
draft = false
title = 'Rust و WebAssembly'
description = 'Rust و WebAssembly: کامپایل به wasm32-unknown-unknown و wasm32-wasip1، رد کردن رشته از مرز wasm به‌صورت دستی و با wasm-bindgen، و کاربردهای wasm.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "wasm", "webassembly", "wasi", "wasm-bindgen", "intermediate"]
cover = { image = "/images/covers/rust-wasm.fa.png", alt = "Rust و WebAssembly", hiddenInSingle = true }
+++

یک تکه منطق کوچک به Rust دارید، مثلاً یک validator یا parser، و می‌خواهید دقیقاً همان کد جایی اجرا شود که باینری بومی (native) اجرا نمی‌کند: داخل یک برنامه‌ی JavaScript یا داخل میزبانی که می‌خواهد افزونه‌هایی را اجرا کند که به آن‌ها اعتماد ندارد. بازنویسی آن در JavaScript یعنی دو نسخه که ممکن است با هم اختلاف پیدا کنند. فرستادن یک کتاب‌خانه‌ی بومی هم کمک نمی‌کند، چون مقصد یک ماشین معمولی نیست.

{{< term "webassembly" "WebAssembly" >}} (به‌اختصار wasm) جواب رایج است. یک قالب دودویی قابل‌حمل برای دستورهاست که روی یک ماشین مجازی ایزوله اجرا می‌شود. یک ماژول wasm خودش به DOM، فایل یا شبکه دسترسی ندارد. فقط **linear memory** خودش را دارد، که یک آرایه‌ی پیوسته از بایت است، و هر تابعی که میزبان (مرورگر، Node یا یک runtime) به آن بدهد.

این مقاله Rust را برای wasm می‌سازد و به چیزی نگاه می‌کند که اول از همه آدم‌ها را غافلگیر می‌کند: از مرز فقط عدد رد می‌شود. رشته را باید در حافظه‌ی ماژول کپی کرد و به‌صورت pointer و طول فرستاد. بعد از [release engineering](/fa/posts/rust-docker-ci-release/) می‌آید: این بار خروجی به‌جای image ‏Docker یک فایل `.wasm` است. در [مقاله‌ی unsafe و FFI](/fa/posts/rust-unsafe-ffi/) با C ABI از یک مرز رد شدیم و Go هم در [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) همین کار را کرد. WebAssembly راه دیگری برای رد شدن از مرز است، با یک sandbox در وسط.

> برای این نسخه‌ی مقاله demoهای `raw` و `wasi` و اندازه‌های Go را دوباره ساختم و اجرا کردم، با `rustc 1.90.0` (edition 2024)، Node نسخه‌ی 20.13.1 و Go نسخه‌ی 1.27.3 روی macOS arm64. ابزار خط فرمان `wasm-bindgen` روی این ماشین نصب نیست و چیزی نصب نکردم، پس بخش `wasm-bindgen` پایین از اجرای اصلی من است، با `wasm-bindgen` نسخه‌ی 0.2.129 (نسخه‌ی قفل‌شده در `Cargo.lock` همان demo). مرورگر هم در دسترس نبود: همه‌چیز از Node بارگذاری شد و درباره‌ی مرورگر ادعایی ندارم. demoها crateهای محلی‌اند: `raw`، `bindgen`، `wasi` و `gohello`.

## ساده‌ترین مسیر: فقط عدد

یک بار targetها را با `rustup target add wasm32-unknown-unknown wasm32-wasip1` اضافه کنید. با `wasm32-unknown-unknown` شروع می‌کنیم، یعنی targetای که اصلاً رابط سیستمی ندارد. نوع crate باید `cdylib` باشد، که باعث می‌شود Cargo یک فایل `.wasm` مستقل بسازد، و تابع‌ها دقیقاً مثل مقاله‌ی FFI هستند:

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

`#[unsafe(no_mangle)]` اسم تابع را همان‌طور که هست نگه می‌دارد تا میزبان بتواند `add` را در exportهای ماژول پیدا کند. یک profile به اسم `small` هم اضافه کردم (`opt-level = "z"`، `lto = true`، `strip = true` و `codegen-units = 1`؛ معنی‌شان در [مقاله‌ی release](/fa/posts/rust-docker-ci-release/) هست) و crate را دو بار ساختم، با `cargo build --release --target wasm32-unknown-unknown` و با `--profile small`. اندازه‌ی `raw.wasm` به بایت این بود:

```text
24161   (release)
10334   (small)
```

این اندازه‌ها شامل تابع‌های رشته‌ی بخش بعد هستند و همان عددهای اجرای اصلی من‌اند.

## رشته به linear memory نیاز دارد

رشته عدد نیست، پس میزبان باید بایت‌هایش را در حافظه‌ی ماژول بگذارد و بعد آدرس و طول را بدهد. ماژول برای این `alloc` و `dealloc` را export می‌کند (از `Layout` با alignment ‏۱ استفاده می‌کنند که برای بایت درست است) و تابعی که بایت‌ها را برمی‌خواند. این تابع خواندن است:

```rust
#[unsafe(no_mangle)]
pub unsafe extern "C" fn count_chars(ptr: *const u8, len: usize) -> usize {
    let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
    std::str::from_utf8(bytes).map(|s| s.chars().count()).unwrap_or(0)
}
```

از pointer و طول یک slice می‌سازد، بررسی می‌کند UTF-8 معتبر باشد و نویسه‌ها (نه بایت‌ها) را می‌شمارد. حالا سمت JavaScript که با `node js/run.mjs <file>` اجرا می‌شود. ماژول را بارگذاری می‌کند، تابع‌های عددی را صدا می‌زند و بعد برای رشته سه کار می‌کند: آن را به UTF-8 کد می‌کند، داخل ماژول با `alloc` جا می‌گیرد و بایت‌ها را آنجا کپی می‌کند، و `count_chars` را صدا می‌زند. (این هسته‌ی اسکریپت است؛ فایل واقعی نام exportها و اندازه‌ی حافظه را هم چاپ می‌کند.)

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

خروجی کامل اسکریپت برای هر دو build (یکسان چاپ کردند):

```text
exports: memory, add, fib, alloc, dealloc, count_chars, __data_end, __heap_base
add(2, 40) = 42
fib(50) = 12586269025n
fib(90) = 2880067194370816120n
bytes=13 chars=9
memory pages: 18
```

خط‌به‌خط:

- `exports` فهرست چیزهایی است که ماژول می‌دهد. جز تابع‌های ما، خود `memory` و دو نشانه (`__data_end` و `__heap_base`) هست که toolchain اضافه می‌کند.
- `add` و `fib` عددهای انتظار‌شده را برمی‌گردانند. به `n` بعد از نتیجه‌های فیبوناچی دقت کنید: `u64` در Rust به‌صورت `BigInt` به JavaScript می‌رسد، چون عدد معمولی JavaScript نمی‌تواند همه‌ی عددهای ۶۴ بیتی را نگه دارد.
- `bytes=13 chars=9`: متن `سلام wasm` ۹ نویسه است، ولی در UTF-8 هر چهار حرف فارسی دو بایت می‌گیرند، پس ۱۳ بایت لازم دارد. ماژول نویسه‌ها را از بایت‌هایی که میزبان کپی کرده بود درست شمرد.
- `memory pages: 18` اندازه‌ی حافظه‌ی ماژول به صفحه‌های ۶۴ کیلوبایتی است. بررسی نکردم چرا ۱۸ است.

این همان انضباط FFI در C است: تخصیص با شماست، pointer فقط یک عدد است و هیچ چیز شما را وارسی نمی‌کند. برای همین باید `dealloc` را صدا بزنید.

## wasm-bindgen: کد چسباننده‌ی تولیدشده

نوشتن این کار با دست برای هر تابع جواب نمی‌دهد. crate و ابزار خط فرمان {{< term "wasm-bindgen" "wasm-bindgen" >}} کد چسباننده را برایتان تولید می‌کنند. تابع Rust معمولی می‌نویسید و علامتش می‌زنید:

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}! Greetings from Rust.")
}
```

اینجا `name` یک `&str` واقعی است و خروجی یک `String` واقعی، و کد تولیدشده همان کپی‌ای را می‌کند که بالا با دست نوشتیم. طبق مستندات wasm-bindgen، ابزار خط فرمان و crate باید یک نسخه باشند؛ در اجرای اصلی من هر دو 0.2.129 بودند. بعد از build برای `wasm32-unknown-unknown`، دستور `wasm-bindgen target/wasm32-unknown-unknown/release/greeter.wasm --target nodejs --out-dir pkg` را اجرا کردم. یک فایل `.js`، یک `.d.ts` (تعریف type‌های TypeScript) و یک `_bg.wasm` ساخت. بعد یک اسکریپت کوچک Node آن را مثل هر کتاب‌خانه‌ی JavaScript صدا می‌زند (تابع `add` را هم صدا می‌زند که خط خروجی‌اش را اینجا نیاورده‌ام):

```text
$ node run.cjs
Hello, Roham! Greetings from Rust.
Hello, سلام! Greetings from Rust.
```

اندازه‌ها، در اجرای اصلی: فایلی که Cargo ساخت (با `opt-level = "z"` و `lto` و `strip`) ۲۷۳۴۷ بایت بود، `greeter_bg.wasm` پردازش‌شده ۱۲۷۱۶ بایت، و JavaScript تولیدشده ۳۷۶۹ بایت اضافه کرد. آن را با نسخه‌ی دستی که همان تابع‌ها را دارد مقایسه نکردم، پس درباره‌ی هزینه‌ی کد چسباننده ادعایی ندارم.

## WASI: wasm بیرون از مرورگر

ماژول `raw` بالا جز محاسبه کاری نمی‌توانست بکند. {{< term "wasi" "WASI" >}} یک رابط سیستمی (فایل، آرگومان خط فرمان، stdin، ساعت) است که میزبان صریحاً به ماژول می‌دهد. یک برنامه‌ی خط فرمان معمولی Rust برای آن به تغییر کد نیاز ندارد، فقط target دیگری. demo یک شمارنده‌ی کلمه‌ی کوچک است که آرگومان‌هایش را چاپ می‌کند، خط‌ها و کلمه‌های stdin را می‌شمارد و بعد می‌کوشد `/data/hello.txt` را بخواند:

```rust
let args: Vec<String> = std::env::args().skip(1).collect();
let mut text = String::new();
std::io::stdin().read_to_string(&mut text).unwrap();
let words = text.split_whitespace().count();
println!("args={args:?} lines={} words={words}", text.lines().count());
if let Ok(path) = std::fs::read_to_string("/data/hello.txt") {
    println!("file says: {}", path.trim());
}
```

دستور `cargo build --release --target wasm32-wasip1` یک `wordcount.wasm` ‏۷۱۲۱۵ بایتی داد (با `opt-level = "z"` و `lto` و `strip` در profile). ماژول `node:wasi` در Node (آزمایشی است: یک هشدار چاپ می‌کند که حذفش کرده‌ام) می‌تواند آن را اجرا کند. اسکریپت میزبان آرگومان‌های `a b` را می‌دهد، stdin را وصل می‌کند و یک پوشه‌ی محلی `data` را به `/data` داخل ماژول نگاشت می‌کند:

```text
$ printf 'one two\nthree\n' | node run.mjs target/wasm32-wasip1/release/wordcount.wasm
args=["a", "b"] lines=2 words=3
file says: hello from the host
```

ورودی دو خط و سه کلمه دارد و برنامه هم آرگومان‌هایش و هم محتوای فایل را چاپ کرد. برنامه `/data/hello.txt` را می‌خواند و این مسیر فقط به این دلیل وجود دارد که میزبان `preopens: { "/data": ... }` را داده. با `preopens: {}` همان ماژول فقط خط اول را چاپ کرد: فایل نامرئی بود. این همان sandbox است که کار می‌کند: ماژول فقط چیزی را می‌بیند که میزبان به آن داده.

## Go روی همین زمین

Go هم می‌تواند wasm بسازد، با `GOOS=js GOARCH=wasm` و `GOOS=wasip1 GOARCH=wasm`. یک hello world را به هر دو شکل ساختم و نسخه‌ی wasip1 را زیر Node WASI اجرا کردم: `hello from Go` چاپ کرد. اندازه‌ها با Go نسخه‌ی 1.27.3 این بود: ۲۵۰۷۶۹۹ بایت (js) و ۲۴۸۰۸۶۲ بایت (wasip1؛ با `-ldflags="-s -w"` برابر ۲۴۳۶۳۳۱). (اجرای اصلی من، با نسخه‌ی قدیمی‌تر Go، برای همین build‌ها حدود ۲٫۶ مگابایت اندازه گرفته بود؛ پس این عددها با نسخه‌ی Go جابه‌جا می‌شوند.) hello world هم‌ارز در Rust، که با `rustc --target wasm32-wasip1 -C opt-level=z -C lto -C strip=symbols` ساخته شد، ۴۲۵۶۵ بایت بود و `hello from Rust` چاپ کرد. برنامه‌ی Go runtime خودش را با خود می‌برد که احتمالاً علت تفاوت است، ولی اندازه نگرفتم کدام بخش غالب است.

## کی wasm منطقی است

- افزونه‌ها و کد نامطمئن: میزبان تصمیم می‌گیرد ماژول به چه چیزی دست بزند.
- اشتراک یک تکه منطق با کد JavaScript (اعتبارسنجی، parse، یک codec).
- runtimeهای edge یا serverless که ماژول wasm می‌پذیرند.

و کی منطقی نیست:

- یک سرویس backend معمولی: باینری بومی ساده‌تر است و پشتیبانی WASI در کتاب‌خانه‌ها (socket، thread) فرق می‌کند.
- کار سنگین با DOM: wasm برایش باز هم از JavaScript رد می‌شود.
- فراخوانی‌های کوچک و پرتکرار با رشته: هر فراخوانی بایت‌ها را از مرز کپی می‌کند.

## پیش از رفتن سراغ wasm

- **نسخه‌ی `wasm-bindgen` باید یکی باشد.** ابزار خط فرمان و crate در `Cargo.toml` باید هم‌نسخه باشند، وگرنه ابزار شکایت می‌کند.
- **بدون کد چسباننده فقط عدد رد می‌شود.** `u64` در JavaScript به `BigInt` تبدیل می‌شود که کدی را که عدد معمولی انتظار دارد غافلگیر می‌کند.
- **چیزی را که `alloc` کرده‌اید آزاد کنید.** ماژول حافظه‌ای را که میزبان خواسته خودش پاک نمی‌کند، پس فراموش کردن `dealloc` نشت می‌دهد.
- **WASI در Node آزمایشی است** و ممکن است عوض شود.
- **اندازه به profile بستگی دارد** (۲۴۱۶۱ در برابر ۱۰۳۳۴ بایت بالا)؛ build خودتان را اندازه بگیرید.

## تمرین

یک تابع export‌شده‌ی `reverse(ptr, len)` اضافه کنید که رشته را در جا برمی‌گرداند و آن را از Node صدا بزنید. بعد مقایسه کنید `wasm-bindgen` چقدر کد کم می‌کند.

## قدم بعدی

«پروژه‌ی پایانی Rust: یک سرویس کامل» تکه‌های قبلی را به هم وصل می‌کند.
