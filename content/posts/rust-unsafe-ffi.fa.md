+++
date = '2027-02-18T10:00:00+03:30'
draft = false
title = 'Unsafe و FFI در Rust'
description = 'unsafe در Rust: قابلیت‌هایی که باز می‌کند، پنهان کردن آن پشت API امن، صدا زدن C از Rust و ساختن کتاب‌خانه‌ی C ABI برای یک برنامه‌ی C.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "unsafe", "ffi", "c", "intermediate"]
cover = { image = "/images/covers/rust-unsafe-ffi.fa.png", alt = "Unsafe و FFI در Rust", hiddenInSingle = true }
+++

می‌خواهیم یک slice را به دو نیمه‌ی قابل‌تغییر تقسیم کنیم، یکی از اول تا `mid` و دیگری از `mid` تا آخر. ما می‌دانیم این دو نیمه روی هم نمی‌افتند، پس تغییر دادن هر دو هم‌زمان مشکلی ندارد. این کد را بنویسیم:

```rust
fn split(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    (&mut s[..mid], &mut s[mid..])
}
```

```text
error[E0499]: cannot borrow `*s` as mutable more than once at a time
 --> c.rs:2:26
  |
1 | fn split(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
  |             - let's call the lifetime of this reference `'1`
2 |     (&mut s[..mid], &mut s[mid..])
  |     ---------------------^--------
  |     |     |              |
  |     |     |              second mutable borrow occurs here
  |     |     first mutable borrow occurs here
  |     returning this value requires that `*s` is borrowed for `'1`
  |
  = help: use `.split_at_mut(position)` to obtain two mutable non-overlapping sub-slices
```

کامپایلر دو بار از `*s` قرض قابل‌تغییر گرفته می‌بیند و رد می‌کند. او از روی `..mid` و `mid..` نمی‌تواند نتیجه بگیرد که دو بازه‌ی جدا هستند؛ قوانین borrow checker فقط به خود `s` نگاه می‌کنند. پیشنهاد آخر پیام می‌گوید از `split_at_mut` استفاده کنید، و `split_at_mut` در کتاب‌خانه‌ی استاندارد از کجا آمده؟ از همان جایی که این مقاله درباره‌اش است: از `unsafe`.

`unsafe` در Rust یعنی «این‌جا کامپایلر نمی‌تواند درستی را ثابت کند؛ من قول می‌دهم درست است». این قول دست خود شماست، و مقاله می‌خواهد نشان بدهد دقیقاً چه چیزی را باز می‌کند، چه چیزی را **نه**، و قول شما چیست. بعدش همین ایده را برای حرف زدن با C به کار می‌بریم: یک کتاب‌خانه‌ی کوچک با **C ABI** (قرارداد باینری که C هم می‌فهمد) می‌سازیم و یک برنامه‌ی C را به آن لینک می‌کنیم.

این مقاله بعد از [ماکروها در Rust](/fa/posts/rust-macros/) می‌آید. آنچه تا این‌جا یاد گرفتیم، [ownership](/fa/posts/rust-ownership/) و [smart pointerها](/fa/posts/rust-smart-pointers/)، چیزهایی است که Rust امن برایتان تضمین می‌کند. `unsafe` جایی است که شما بخشی از آن تضمین را خودتان به عهده می‌گیرید. Go هم چیزی شبیه این را با پکیج `unsafe` دارد ([مقاله‌ی pointerها](/fa/posts/go-pointers-memory/)).

> همه‌ی کدهای زیر را با Rust 1.90 (`rustc 1.90.0`)، edition 2024 و روی macOS (arm64) با `cc` (Apple clang) دوباره کامپایل و اجرا کرده‌ام. دمو در دو crate محلی است: `unsafe-demo` و `ffi-lib`، هر دو بدون وابستگی خارجی. چند مثال کوچک (خطاهای `split`، deref بدون `unsafe`، `static mut` با `println!` و `unsafe fn`) را فقط برای نمایش خطا در برنامه‌های جدا نوشتم و اجرا کردم. از پیام‌های خطا خط‌های `note:` و «For more information…» را حذف کرده‌ام. **Miri** (مفسری که {{< term "undefined-behavior" "UB" >}} را پیدا می‌کند) روی این ماشین نصب نیست، پس هیچ‌کدام از کدها را با آن اجرا نکرده‌ام.

## `unsafe` چه چیزی را باز می‌کند؟

داخل یک بلوک `unsafe` یا یک `unsafe fn` دقیقاً **پنج** کار اضافه مجاز می‌شود (طبق Rust Book و Rust Reference):

1. deref کردن یک {{< term "raw-pointer" "raw pointer" >}}
2. صدا زدن یک تابع `unsafe`
3. خواندن یا نوشتن یک `static mut`
4. پیاده‌سازی یک trait از نوع `unsafe`
5. خواندن فیلدهای یک `union`

این پنج کار چیز مشترکی دارند: کامپایلر نمی‌تواند درستی‌شان را بسنجد. اگر بدون `unsafe` امتحان کنید، خطا می‌گیرید:

```text
error[E0133]: dereference of raw pointer is unsafe and requires unsafe block
 --> a.rs:4:20
  |
4 |     println!("{}", *p);
  |                    ^^ dereference of raw pointer
```

```text
error[E0133]: call to unsafe function `abs` is unsafe and requires unsafe block
 --> d.rs:6:20
  |
6 |     println!("{}", abs(-5));
  |                    ^^^^^^^ call to unsafe function
```

هر دو پیام یک چیز را می‌گویند: «این کار unsafe است و بلوک `unsafe` می‌خواهد». هر پنج مورد را در یک برنامه ببینیم:

```rust
static mut COUNTER: u32 = 0;

#[repr(C)]
union IntOrFloat { i: u32, f: f32 }

unsafe trait Zeroable {}
unsafe impl Zeroable for u32 {}

fn zeroed<T: Zeroable>() -> T {
    // SAFETY: Zeroable promises that all-zero bytes are a valid T.
    unsafe { std::mem::zeroed() }
}

unsafe fn read_twice(p: *const i32) -> (i32, i32) {
    unsafe { (*p, *p) }
}

fn main() {
    let mut x = 10;
    let (r1, r2) = (&raw const x, &raw mut x);   // raw pointers
    unsafe { *r2 += 1; println!("raw: {} {}", *r1, *r2); }
    println!("{:?}", unsafe { read_twice(&x) });
    unsafe { COUNTER += 1; COUNTER += 1; let c = COUNTER; println!("COUNTER = {c}"); }
    let z: u32 = zeroed();
    let u = IntOrFloat { f: 1.0 };
    println!("zeroed = {z}, 1.0f32 bits = {:#x}", unsafe { u.i });
}
```

```text
raw: 11 11
(11, 11)
COUNTER = 2
zeroed = 0, 1.0f32 bits = 0x3f800000
```

یکی‌یکی:

- **Raw pointer** (`*const T` و `*mut T`): یک آدرس خالی. `&raw const x` و `&raw mut x` از روی `x` دو تا می‌سازند. ساختن raw pointer امن است (من در demo از عدد `0x1234` یکی ساختم و چاپش کردم و `unsafe` لازم نشد)؛ فقط deref کردنش امن نیست، چون کسی چک نکرده که به حافظه‌ی معتبر اشاره می‌کند. raw pointer نه lifetime دارد، نه قانون borrow، و می‌تواند null باشد. به همین دلیل `*r2 += 1` و `*r1` هر دو در یک بلوک `unsafe` است و هر دو ۱۱ را می‌بینند: دو اشاره‌گر به یک متغیر، که با `&mut` و `&` معمولی ممکن نبود.
- **تابع `unsafe`** (`read_twice`): تابعی که ایمنی‌اش به قراردادی بستگی دارد که فراخواننده باید رعایت کند (اینجا: `p` باید اشاره‌گر معتبری به یک `i32` باشد). صدا زدنش بلوک `unsafe` می‌خواهد. خط دوم خروجی، `(11, 11)`، نتیجه‌ی آن است.
- **`static mut`**: متغیر سراسری قابل‌تغییر. چون هر thread می‌تواند در هر لحظه به آن دست بزند، Rust نمی‌تواند {{< term "data-race" "data race" >}} را رد کند و شما مسئولید. دقت کنید که `let c = COUNTER;` را جدا نوشتم و داخل `println!` ننوشتم `COUNTER`. دلیلش این است که `println!` به آرگومانش reference می‌گیرد و در edition 2024 گرفتن reference به `static mut` خطای کامپایل است (یک lint که در این edition به‌طور پیش‌فرض خطا است):

  ```text
  error: creating a shared reference to mutable static
   --> b.rs:6:24
    |
  6 |         println!("{}", COUNTER);
    |                        ^^^^^^^ shared reference to mutable static
  ```

  خواندن مقدار در یک متغیر محلی (`let c = COUNTER;`) از این مشکل رد می‌شود.
- **`unsafe trait`** (`Zeroable`): trait‌ای که خود پیاده‌سازی‌اش یک قول است: «بایت‌های صفر برای این نوع یک مقدار معتبر است». کدی که `std::mem::zeroed()` را صدا می‌زند به همین قول تکیه می‌کند. `unsafe impl Zeroable for u32` یعنی من این قول را برای `u32` می‌دهم (و برای `u32` درست است).
- **`union`**: مثل struct است ولی همه‌ی فیلدها روی یک حافظه‌اند. نوشتن `f: 1.0` و خواندن `i` یعنی «بیت‌های `1.0f32` را به‌عنوان عدد صحیح ببین»، که `0x3f800000` است. کامپایلر نمی‌داند کدام فیلد در حال حاضر معتبر است، پس خواندنش unsafe است.

## `unsafe` چه چیزی را خاموش **نمی‌کند**؟

یک سوءتفاهم رایج: «داخل `unsafe` همه‌ی چک‌ها خاموش است». این درست نیست. فقط همان پنج کار اضافه مجاز می‌شود. بقیه‌ی قوانین، از جمله borrow checker روی reference‌های معمولی، همچنان کار می‌کنند:

```rust
let mut v = vec![1, 2, 3];
unsafe {
    let first = &v[0];
    v.push(4);
    println!("{first}");
}
```

```text
warning: unnecessary `unsafe` block
 --> bc_still_on.rs:3:5
  |
3 |     unsafe {
  |     ^^^^^^ unnecessary `unsafe` block

error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> bc_still_on.rs:5:9
  |
4 |         let first = &v[0];
  |                      - immutable borrow occurs here
5 |         v.push(4);
  |         ^^^^^^^^^ mutable borrow occurs here
6 |         println!("{first}");
  |                    ----- immutable borrow later used here
```

دو چیز در پیام دیده می‌شود. اول، کامپایلر هشدار می‌دهد که این بلوک `unsafe` اصلاً لازم نبود، چون هیچ‌یک از پنج کار در آن نیست. دوم، همان خطای معمول borrow checker را می‌گیریم: `first` یک reference به `v` است، `v.push` به `v` قرض قابل‌تغییر می‌دهد، و بعد از آن `first` دوباره استفاده می‌شود. بلوک `unsafe` هیچ‌چیز را عوض نکرد.

پس در عمل «سرزمین بدون قانون» نیست. اما در همان پنج کار، مسئولیت با شماست. اگر قولتان را بشکنید، به **undefined behavior** (UB، رفتار تعریف‌نشده) می‌رسید. یعنی خود زبان هیچ تعهدی درباره‌ی رفتار برنامه ندارد و کامپایلر حق دارد فرض کند چنین چیزی هرگز اتفاق نمی‌افتد. نتیجه می‌تواند crash باشد، می‌تواند خروجی غلط باشد و می‌تواند ظاهراً درست کار کند تا روزی که کامپایلر یا ماشین عوض شود. طبق Rust Reference نمونه‌هایش: deref کردن اشاره‌گر معلق (جایی که دیگر معتبر نیست) یا نامرتب‌شده (misaligned)، دو `&mut` زنده به یک داده، data race، و ساختن مقداری که برای نوعش معتبر نیست (مثلاً یک `bool` با مقدار ۳). من هیچ‌کدام از این‌ها را اجرا نکرده‌ام و خروجی‌ای از UB نشان نمی‌دهم: نتیجه‌اش از اجرایی به اجرای دیگر فرق دارد و چیزی را ثابت نمی‌کند.

## `unsafe fn` و بلوک `unsafe`: دو نقش مختلف

کلمه‌ی `unsafe` دو معنای مکمل دارد:

- روی **تعریف** (`unsafe fn`، `unsafe trait`): «برای استفاده از این، فراخواننده باید یک شرط را رعایت کند». این شرط را در مستندات، در بخشی به اسم `# Safety`، بنویسید.
- روی **استفاده** (بلوک `unsafe { ... }`): «من شرط را رعایت کرده‌ام». دلیلش را بالای بلوک در یک کامنت `// SAFETY:` بنویسید.

در edition 2024 این دو حتی از هم جدا هستند: بدنه‌ی یک `unsafe fn` خودش «امن» حساب می‌شود و برای کار unsafe داخلش هم بلوک `unsafe` می‌خواهد. به همین خاطر `read_twice` بالا یک `unsafe { (*p, *p) }` داخل خودش دارد. اگر آن را برنداریم:

```rust
unsafe fn read_first(p: *const i32) -> i32 {
    *p
}
```

```text
warning[E0133]: dereference of raw pointer is unsafe and requires unsafe block
 --> e.rs:2:5
  |
2 |     *p
  |     ^^ dereference of raw pointer
  |
note: an unsafe function restricts its caller, but its body is safe by default
```

(در این مثال، فراخوانی `read_first(&x)` از `main` هم همان خطای E0133 را داد، چون صدا زدن تابع `unsafe` بلوک می‌خواهد.) جمله‌ی `note` همین را می‌گوید: `unsafe fn` فقط فراخواننده را محدود می‌کند و بدنه به‌طور پیش‌فرض امن است.

## یک abstraction امن: برگردیم به `split_at_mut`

الگوی خوب این است: یک هسته‌ی کوچک `unsafe`، پشت یک تابع **امن**. فراخواننده‌ها هیچ‌وقت `unsafe` نمی‌نویسند و فقط یک جا باید درستی را اثبات کرد. این همان کاری است که `split_at_mut` در کتاب‌خانه‌ی استاندارد می‌کند. من برای نشان دادن، نسخه‌ی خودم را نوشتم:

```rust
pub fn my_split_at_mut(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    let len = s.len();
    assert!(mid <= len, "mid out of range");
    let ptr = s.as_mut_ptr();
    // SAFETY: mid <= len, so [0, mid) and [mid, len) are in bounds and do not
    // overlap; `s` is mutably borrowed for the returned lifetime, so nothing
    // else can touch the memory meanwhile.
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

بخوانیم:

1. `assert!(mid <= len, ...)` شرطی را چک می‌کند که کد پایین به آن تکیه دارد. اگر `mid` بزرگ‌تر باشد، برنامه panic می‌کند، پیش از آنکه چیزی خراب شود. همین چک است که تابع را برای **هر** فراخواننده امن می‌کند.
2. `s.as_mut_ptr()` اشاره‌گر خام به اولین عنصر را می‌دهد.
3. `from_raw_parts_mut(ptr, mid)` از آدرس شروع و طول، یک slice می‌سازد: نیمه‌ی اول. `from_raw_parts_mut(ptr.add(mid), len - mid)` نیمه‌ی دوم را از وسط شروع می‌کند.
4. کامنت `SAFETY:` می‌گوید چرا این درست است: دو بازه داخل slice‌اند، روی هم نمی‌افتند، و چون `s` برای مدت عمر نتیجه قرض قابل‌تغییر شده، کس دیگری به آن حافظه دست نمی‌زند.

سه تست نوشتم: split معمولی، `mid = 0`، و یک حالت `should_panic` برای `mid > len`. هر سه پاس شدند (`3 passed`). در `main` هم `[1,2,3,4,5]` را در ۲ تقسیم کردم، اولین عنصر هر نیمه را عوض کردم و `[100, 2, 300, 4, 5]` چاپ شد.

## صدا زدن C از Rust

حالا همان ایده برای زبان دیگر. {{< term "rust-ffi" "FFI" >}} (Foreign Function Interface) یعنی صدا زدن کدی که به زبان دیگری نوشته شده. Rust با C از طریق **C ABI** حرف می‌زند، یعنی قراردادی درباره‌ی اینکه آرگومان‌ها چطور به تابع می‌رسند و نتیجه چطور برمی‌گردد. هر تابع C که از Rust صدا می‌زنیم برای کامپایلر ناشناخته است، پس صدا زدنش `unsafe` است.

تعریف تابع خارجی داخل بلوک `unsafe extern` است. در edition 2024 همان `extern "C" { }` ساده رد می‌شود. (در بخش بعد نمایش این خطا را می‌بینید.) برای رشته‌های C به `CString` (رشته‌ی مالک با NUL پایانی) و `CStr` (نمای قرضی) نیاز داریم:

```rust
unsafe extern "C" {
    fn abs(x: i32) -> i32;
    fn strlen(s: *const c_char) -> usize;
}

let s = CString::new("hello").unwrap();
println!("abs(-5) = {}", unsafe { abs(-5) });
println!("strlen = {}", unsafe { strlen(s.as_ptr()) });
println!("{:?}", unsafe { CStr::from_ptr(s.as_ptr()) }.to_str());
```

```text
abs(-5) = 5
strlen = 5
back to Rust: Ok("hello")
```

`abs` و `strlen` از کتاب‌خانه‌ی C سیستم می‌آیند و نیازی به لینک اضافه نداشتند. `strlen` یک `*const c_char` می‌خواهد، یعنی آدرس رشته‌ای که با بایت صفر (NUL) تمام می‌شود. `CString` همان NUL پایانی را اضافه می‌کند و `as_ptr()` آدرسش را می‌دهد. خط آخر مسیر برگشت است: `CStr::from_ptr` آدرس را دوباره به یک رشته‌ی قرضی تبدیل می‌کند و `to_str()` آن را به `&str` تبدیل می‌کند (که `Ok("hello")` شد، چون UTF-8 معتبر است).

یک تله: رشته‌ی C در اولین NUL تمام می‌شود، پس `CString::new` رشته‌ای که وسطش NUL دارد را قبول نمی‌کند. `CString::new("he\0llo")` مقدار `Err` برمی‌گرداند که چاپش می‌شود `nul byte found in provided data at position: 2`. دلیلش این است که C فقط `he` را می‌دید و بقیه را بی‌صدا می‌انداخت.

## ارائه‌ی Rust به C

حالا جهت برعکس: کد Rust را طوری بسازیم که یک برنامه‌ی C صدایش بزند. crate به اسم `ffi-lib` در `Cargo.toml` مقدار `crate-type = ["cdylib", "staticlib"]` دارد: یعنی کتاب‌خانه‌ی پویا (`.dylib` روی macOS) و ایستا (`.a`) برای C بسازد. سه چیز لازم است:

- `extern "C"` تا تابع با C ABI صدا زده شود.
- `#[unsafe(no_mangle)]` تا اسم تابع در فایل ساخته‌شده همان `add` بماند و کامپایلر آن را به اسم درهم‌ریخته‌ی داخلی تبدیل نکند.
- `#[repr(C)]` روی هر struct که از مرز رد می‌شود، تا چیدمان حافظه‌اش مثل C باشد.

در edition 2024 این `unsafe(...)` دور attribute لازم است. شکل قدیمی را امتحان کردم:

```text
error: unsafe attribute used without unsafe
 --> old_syntax.rs:1:3
  |
1 | #[no_mangle]
  |   ^^^^^^^^^ usage of unsafe attribute
  |
help: wrap the attribute in `unsafe(...)`

error: extern blocks must be unsafe
 --> old_syntax.rs:3:1
  |
3 | extern "C" { fn abs(x: i32) -> i32; }
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

(پیشنهاد اصلاح کامپایلر زیر `help:` را کوتاه کرده‌ام.) کتاب‌خانه:

```rust
#[repr(C)]
pub struct Point { pub x: f64, pub y: f64 }

#[unsafe(no_mangle)]
pub extern "C" fn add(a: i32, b: i32) -> i32 { a.wrapping_add(b) }

#[unsafe(no_mangle)]
pub unsafe extern "C" fn greet(name: *const c_char) -> *mut c_char {
    catch_unwind(|| {
        if name.is_null() { return std::ptr::null_mut(); }
        // SAFETY: caller promised a valid NUL-terminated string.
        let Ok(name) = unsafe { CStr::from_ptr(name) }.to_str() else { return std::ptr::null_mut() };
        CString::new(format!("Hello, {name}!")).map_or(std::ptr::null_mut(), CString::into_raw)
    }).unwrap_or(std::ptr::null_mut())
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn free_string(s: *mut c_char) {
    if !s.is_null() {
        // SAFETY: `s` came from CString::into_raw in `greet`, freed once.
        drop(unsafe { CString::from_raw(s) });
    }
}
```

چند نکته:

- در `add` از `wrapping_add` استفاده شده تا سرریز نتیجه‌ی تعریف‌شده داشته باشد (در حالت debug سرریز معمولی panic می‌کند و در تابعی که به C صدا زده می‌شود panic خوب نیست؛ ادامه را ببینید).
- `greet` یک رشته‌ی C می‌گیرد و یک رشته‌ی جدید روی heap برمی‌گرداند. NULL را چک می‌کند، چون C این را برای شما نمی‌کند. `CString::into_raw` مالکیت رشته را از Rust می‌گیرد و فقط آدرس را به C می‌دهد.
- تابع `unsafe extern "C"` است و بخش `# Safety` دارد (در کد اصلی): ایمنی `name` را فراخواننده‌ی C تضمین می‌کند.
- تابع `checksum(const uint8_t*, size_t)` (هش FNV-1a) با `slice::from_raw_parts` از آدرس و طول یک slice می‌سازد، و `point_length` و `point_scale` یک `Point` را به‌ترتیب by value و با اشاره‌گر می‌گیرند. هدر `ffi_lib.h` را دستی نوشتم.

مهم‌ترین قانون **مالکیت حافظه** است: حافظه را باید همان allocator‌ای آزاد کند که ساخته. `greet` با allocator خود Rust حافظه می‌گیرد، پس C باید آن را با `free_string` برگرداند، نه با `free()`. آزاد کردن دوباره‌ی همان اشاره‌گر هم double free و UB است؛ اجرایش نکردم.

قانون دوم درباره‌ی panic است. اگر panic از داخل تابع Rust به کد C برسد، C هیچ چیزی از آن نمی‌داند. برای همین `greet` بدنه‌اش را در `catch_unwind` می‌گذارد و به‌جای panic، NULL برمی‌گرداند. برای دیدن اینکه بدون آن چه می‌شود، یک `extern "C" fn` ساده که panic می‌کند ساختم. در این نسخه‌ی Rust، unwind نمی‌شود و runtime برنامه را abort می‌کند:

```text
about to panic inside extern "C"

thread 'main' panicked at panic_abort.rs:3:5:
oops
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

(خط‌های `note:` و stack trace را حذف کرده‌ام، چون stack trace مسیرهای ماشین من را دارد.) کد خروج برنامه ۱۳۴ بود، یعنی سیگنال SIGABRT.

## لینک کردن برنامه‌ی C

برنامه‌ی C همه‌ی تابع‌ها را صدا می‌زند. بخش مهمش مالکیت رشته است: C آن را از `greet` می‌گیرد، چاپ می‌کند و باید به `free_string` پس بدهد:

```c
char *g = greet("Roham");
printf("greet: %s\n", g);
free_string(g);
```

اول کتاب‌خانه را با `cargo build --release` می‌سازیم. `nm -gU` نام تابع‌های export شده‌ی `.dylib` را نشان می‌دهد (آدرس‌ها را حذف کرده‌ام). بعد برنامه‌ی C را با کتاب‌خانه‌ی ایستا لینک و اجرا می‌کنیم:

```text
$ cargo build --release
$ nm -gU target/release/libffi_lib.dylib
T _add   T _checksum   T _free_string   T _greet   T _point_length   T _point_scale
$ cc main.c -I. target/release/libffi_lib.a -o main_static && ./main_static
add(2, 40) = 42
greet: Hello, Roham!
checksum("hello") = 11831194018420276491
length = 5.0
scaled = (6.0, 8.0)
```

نماد `T` یعنی تابع در بخش کد کتاب‌خانه قرار دارد و بیرون دیده می‌شود. شش تابعی که با `#[unsafe(no_mangle)]` علامت زدیم دقیقاً همین‌ها هستند. خروجی را بخوانیم: `add(2, 40)` برابر ۴۲، رشته‌ای که Rust ساخت و C چاپ کرد و بعد به Rust برگرداند، هش FNV-1a کلمه‌ی `hello`، طول بردار (3, 4) که ۵ است، و همان بردار بعد از دو برابر شدن که `(6.0, 8.0)` است (`point_scale` آن را همان‌جا و با اشاره‌گر عوض کرد). لینک با `.dylib` و `-lffi_lib` هم همین پنج خط را داد. این کتاب‌خانه را بعداً برای صدا زدن از Go دوباره استفاده می‌کنیم.

## چطور کد `unsafe` را بررسی کنیم؟

تست‌ها فقط نشان می‌دهند که مسیرهایی که امتحان کردید کار می‌کنند. برای کد `unsafe` ابزار دیگری هم هست: Miri، مفسری که برنامه را قدم‌به‌قدم اجرا می‌کند و هنگام UB (مثلاً دسترسی خارج از محدوده یا اشاره‌گر معلق) متوقف می‌شود. از sanitizerها هم می‌شود استفاده کرد. هیچ‌کدام روی این ماشین نصب نیست، پس اجرایشان نکردم؛ ولی برای کدی که `unsafe` زیاد دارد پیشنهاد می‌کنم حتماً با Miri اجرا شود.

## قواعد مرز `unsafe`

- **`unsafe` borrow checker را خاموش نمی‌کند.** فقط پنج کار را مجاز می‌کند و مسئولیتشان را به شما می‌دهد (دمو بالا با `E0502` این را نشان داد).
- **بلوک‌های `unsafe` را کوچک نگه دارید** و روی هرکدام `// SAFETY:` بنویسید. بقیه‌ی برنامه‌تان را ببرید پشت یک تابع امن.
- **هرگز حافظه را با allocator اشتباه آزاد نکنید و هرگز دو بار آزاد نکنید.** هر چیزی که Rust می‌سازد، Rust هم باید آزاد کند.
- **هرگز اجازه ندهید panic از مرز `extern "C"` رد شود.** از `catch_unwind` و کد خطا یا NULL استفاده کنید.
- **اشاره‌گر و طول را در مرز اعتبارسنجی کنید** (چک null)، چون C این کار را برای شما نمی‌کند.

## تمرین

1. تابع `fn reverse_in_place(data: *mut u8, len: usize)` را به `ffi-lib` اضافه کنید و از C صدایش بزنید.
2. یک تابع امن `fn my_swap(a: &mut [i32], i: usize, j: usize)` با raw pointer و یک تست بنویسید.

## قدم بعدی

«پرفورمنس و benchmark با Criterion در Rust»: حالا که کار می‌کند، چقدر سریع است؟
