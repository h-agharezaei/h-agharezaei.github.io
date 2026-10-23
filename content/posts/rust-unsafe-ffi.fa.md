+++
date = '2027-02-18T10:00:00+03:30'
draft = false
title = 'Unsafe و FFI در Rust'
description = 'unsafe در Rust: قابلیت‌هایی که باز می‌کند، پنهان کردن آن پشت API امن، صدا زدن C از Rust و ساختن کتاب‌خانه‌ی C ABI برای یک برنامه‌ی C.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "unsafe", "ffi", "c", "intermediate"]
cover = { image = "/images/covers/rust-unsafe-ffi.fa.png", alt = "Unsafe و FFI در Rust", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/rust-macros/) درباره‌ی macroها بود. این مقاله درباره‌ی دریچه‌ی فرار است: `unsafe`. هر چه تا اینجا یاد گرفتیم ([ownership](/fa/posts/rust-ownership/) و [smart pointerها](/fa/posts/rust-smart-pointers/)) همان چیزی است که Rust امن برایتان تضمین می‌کند. `unsafe` یعنی «این تضمین‌ها را خودم رعایت می‌کنم»، آن هم جایی که کامپایلر نمی‌تواند چک کند، بیشتر برای حرف زدن با C. Go هم همین ایده را با پکیج `unsafe` و `unsafe.Pointer` دارد ([مقاله‌ی pointerها](/fa/posts/go-pointers-memory/)). اینجا یک کتاب‌خانه‌ی کوچک با **C ABI** می‌سازیم و یک برنامه‌ی C را به آن لینک می‌کنیم.

> همه‌ی کدهای زیر با Rust 1.90، edition 2024 و روی macOS کامپایل و اجرا شده‌اند. دمو در دو crate محلی است: `unsafe-demo` و `ffi-lib`.

## پنج قابلیت ویژه

داخل بلوک یا تابع `unsafe` دقیقاً پنج کار اضافه می‌توانید بکنید: deref کردن raw pointer، صدا زدن تابع unsafe، دسترسی به static قابل‌تغییر، پیاده‌سازی trait از نوع unsafe و دسترسی به فیلدهای union. هر پنج تا در یک برنامه:

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

`*const T` و `*mut T` همان **raw pointer**ها هستند. ساختنشان امن است (من از آدرس `0x1234` یکی ساختم و `unsafe` لازم نشد)؛ فقط deref کردن امن نیست، چون کسی چک نکرده که به حافظه‌ی معتبر اشاره می‌کند. raw pointer نه lifetime دارد نه قانون borrow، و می‌تواند null باشد.

نکته‌ی مهم: `unsafe` **borrow checker را خاموش نمی‌کند**. فقط همان پنج کار را باز می‌کند. reference‌های معمولی داخل بلوک `unsafe` هم همچنان چک می‌شوند:

```rust
let mut v = vec![1, 2, 3];
unsafe {
    let first = &v[0];
    v.push(4);
    println!("{first}");
}
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
```

داخل بلوک مسئولیت با شماست: **undefined behavior** (UB) با هر قول شکسته ممکن است، مثل pointer معلق یا نامرتب‌شده، یا دو `&mut` زنده به یک داده.

## یک abstraction امن

الگوی خوب این است: هسته‌ی کوچک `unsafe` پشت یک تابع امن. `split_at_mut` کتاب‌خانه‌ی استاندارد نمونه‌ی کلاسیک است؛ borrow checker نمی‌بیند که دو نیمه‌ی یک slice روی هم نمی‌افتند، برای همین نسخه‌ی خودم را نوشتم:

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

`assert!` است که تابع را برای هر caller امن می‌کند. سه تست نوشتم: split معمولی، `mid = 0` و یک حالت `should_panic` برای `mid > len`؛ هر سه پاس شدند، و `[1,2,3,4,5]` با split در ۲ و ویرایش شد `[100, 2, 300, 4, 5]`. قرارداد: روی هر بلوک `// SAFETY:` و روی هر `unsafe fn` یک بخش `# Safety` در مستندات.

## صدا زدن C از Rust

تعریف تابع خارجی داخل بلوک `unsafe extern` است؛ در edition 2024 همان `extern "C" { }` ساده رد می‌شود. برای رشته‌های C به `CString` (مالک، با NUL پایانی) و `CStr` (قرضی) نیاز داریم:

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
Ok("hello")
```

تله: رشته‌ی C در اولین NUL تمام می‌شود، پس `CString::new` رشته‌ی دارای NUL میانی را قبول نمی‌کند. `CString::new("he\0llo")` مقدار `Err` برمی‌گرداند که چاپش می‌شود `nul byte found in provided data at position: 2`.

## ارائه‌ی Rust از طریق C ABI

crate به اسم `ffi-lib` مقدار `crate-type = ["cdylib", "staticlib"]` دارد. در edition 2024 attribute به شکل `#[unsafe(no_mangle)]` است؛ شکل قدیمی `#[no_mangle]` خطای `unsafe attribute used without unsafe` می‌دهد و بلوک `extern` قدیمی خطای `extern blocks must be unsafe`. داده‌ای که از مرز رد می‌شود باید با C سازگار باشد، یعنی `#[repr(C)]`:

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

تابع `checksum(const uint8_t*, size_t)` (هش FNV-1a) با `slice::from_raw_parts` یک slice می‌سازد، و `point_length` و `point_scale` یک `Point` را by value و با pointer می‌گیرند. هدر `ffi_lib.h` را دستی نوشتم.

قانون مهم **ownership** است: حافظه را باید همان allocator‌ای آزاد کند که ساخته. `greet` با allocator خود Rust حافظه می‌گیرد، پس C باید آن را با `free_string` برگرداند، نه `free()`. آزاد کردن دوباره‌ی همان pointer **double free** و UB است، اجرایش نکردم. panic هم نباید به داخل C unwind شود: `greet` بدنه‌اش را در `catch_unwind` می‌گذارد و NULL برمی‌گرداند. برای نمایش امن: یک `extern "C" fn` ساده که panic می‌کند unwind نمی‌شود و runtime برنامه را abort می‌کند:

```text
about to panic inside extern "C"
thread 'main' panicked at panic_abort.rs:3:5:
oops
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

کد خروج ۱۳۴ بود (SIGABRT).

## لینک کردن برنامه‌ی C

```c
char *g = greet("Roham");
printf("greet: %s\n", g);
free_string(g);
```

```text
$ cargo build --release
$ nm -gU target/release/libffi_lib.dylib
... T _add   T _checksum   T _free_string   T _greet   T _point_length   T _point_scale
$ cc main.c -I. target/release/libffi_lib.a -o main_static && ./main_static
add(2, 40) = 42
greet: Hello, Roham!
checksum("hello") = 11831194018420276491
length = 5.0
scaled = (6.0, 8.0)
```

لینک با `.dylib` و `-lffi_lib` هم همین خروجی را داد. این کتاب‌خانه را بعداً برای صدا زدن از Go دوباره استفاده می‌کنیم.

برای بررسی کد `unsafe` واقعی از Miri (مفسری که UB را پیدا می‌کند) و sanitizerها (مثل AddressSanitizer) استفاده کنید. هر دو toolchain از نوع nightly می‌خواهند، پس اینجا اجرایشان نکردم.

## چند نکته‌ی مهم

- `unsafe` borrow checker را خاموش نمی‌کند؛ مسئولیت پنج عملیات را به شما می‌دهد.
- بلوک‌های `unsafe` را کوچک نگه دارید و روی هرکدام `// SAFETY:` بنویسید.
- هرگز حافظه را با allocator اشتباه آزاد نکنید و هرگز دو بار آزاد نکنید.
- هرگز اجازه ندهید panic از مرز `extern "C"` رد شود؛ از `catch_unwind` و کد خطا یا NULL استفاده کنید.
- pointer و طول را در مرز اعتبارسنجی کنید (چک null)، چون C این کار را نمی‌کند.

## تمرین

۱. تابع `fn reverse_in_place(data: *mut u8, len: usize)` را به `ffi-lib` اضافه کنید و از C صدایش بزنید.
۲. یک تابع امن `fn my_swap(a: &mut [i32], i: usize, j: usize)` با raw pointer و یک تست بنویسید.

## قدم بعدی

مقاله‌ی بعد: بررسی کارایی و benchmark با Criterion در Rust.
