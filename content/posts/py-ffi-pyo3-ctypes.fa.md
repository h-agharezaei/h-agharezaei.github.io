+++
date = '2027-05-24T10:00:00+03:30'
draft = false
title = 'صدا زدن Rust از Python با ctypes و PyO3'
description = 'صدا زدن Rust از Python با ctypes و PyO3: C ABI، آزاد کردن حافظه، panic، maturin، exception، رها کردن GIL، wheel با abi3 و زمان‌هایی که نباید.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "rust", "ffi", "ctypes", "pyo3", "maturin"]
cover = { image = "/images/covers/py-ffi-pyo3-ctypes.fa.png", alt = "صدا زدن Rust از Python با ctypes و PyO3", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-data-csv-sqlite/) در کتابخانه‌ی استاندارد ماندیم. گاهی یک حلقه‌ی داغ در Python کند است و شما از قبل Rust دارید. این مقاله‌ی آخر سری Python دو راه {{< term "ffi" "FFI" >}} برای صدا زدن Rust نشان می‌دهد: `ctypes` (بدون مرحله‌ی build در سمت Python) و {{< term "pyo3" "PyO3" >}} با maturin (یک ماژول واقعی). قواعد مرز همان‌هایی است که در [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) و [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) دیدیم.

> Python 3.14.0، Rust 1.90، macOS arm64، {{< term "uv" "uv" >}} 0.10.9، maturin 1.15.0 و PyO3 با pin روی `=0.30.1`. همه‌چیز اجرا شده. load ماشین ۶ بود، پس **هیچ زمانی** منتشر نمی‌کنم.

## بخش ۱: ctypes و {{< term "abi" "ABI" >}} زبان C

یک کرِیت `cdylib` توابع `extern "C"` را با `#[no_mangle]` منتشر می‌کند: `add(i32, i32)`، `big() -> i64` (مقدار ۵٬۰۰۰٬۰۰۰٬۰۰۰ را برمی‌گرداند)، `checksum(*const u8, usize)` (از نوع FNV-1a)، `greet` (رشته‌ای روی heap برمی‌گرداند) و `free_string`. در macOS کتابخانه `libdemo.dylib` است (در Linux `.so`). بارگذاری و اعلام نوع‌ها:

```python
lib = ctypes.CDLL("<tmp>/libdemo.dylib")
lib.add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.add.restype = ctypes.c_int32
lib.checksum.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
lib.checksum.restype = ctypes.c_uint64
```

```text
add(2, 40) = 42
checksum(b'hello') = 11831194018420276491
python fnv-1a      = 11831194018420276491
```

بدون اعلام، ctypes حدس می‌زند و حدسش `int` است. `big()` یک `int64` برمی‌گرداند:

```text
big() with default restype: 705032704
big() with c_int64:         5000000000
```

۵٬۰۰۰٬۰۰۰٬۰۰۰ منهای 2^32 می‌شود ۷۰۵٬۰۳۲٬۷۰۴: کوتاه‌شدن بی‌صدا. همین پیش‌فرض `add(1, 2, 3, 4)` را هم بی‌صدا پذیرفت. پس همیشه `argtypes` و `restype` را تنظیم کنید.

## رشته‌ها و مالکیت

`greet` حافظه‌ای برمی‌گرداند که Rust اختصاص داده، پس Python باید آن را به `free_string` پس بدهد، نه به `free` زبان C. این همان قاعده‌ی allocator در مقاله‌ی Go است. یک تله: اگر `restype` برابر `c_char_p` باشد ctypes به `bytes` کپی می‌کند و اشاره‌گری که باید آزاد شود را از دست می‌دهید. از `c_void_p` استفاده کنید:

```python
lib.greet.restype = ctypes.c_void_p
p = lib.greet(b"Roham")
print(ctypes.string_at(p).decode())  # Hello, Roham!
lib.free_string(p)
```

callback با `CFUNCTYPE` کار می‌کند؛ شیء callback را تا پایان فراخوانی زنده نگه دارید. `each_square(4, cb)` باعث شد Python این را ثبت کند: `[(0, 0), (1, 1), (2, 4), (3, 9)]`.

## وقتی panic از مرز رد می‌شود

تابع `boom()` را که panic می‌کند اضافه کردم و در یک subprocess اجرا کردم. Rust جدید اجازه نمی‌دهد unwind از `extern "C"` بیرون بزند:

```text
exit code -6
calling boom()
thread '<unnamed>' panicked at src/lib.rs:49:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

`-6` یعنی SIGABRT: کل پروسه‌ی Python مرد و هیچ `except`ای نمی‌تواند بگیرد. راه‌حل `catch_unwind` داخل تابع Rust و برگرداندن مقدار خطا (`-1` یا اشاره‌گر null) است که فراخواننده چک کند؛ `boom_safe()` مقدار `-1` برگرداند.

## بخش ۲: PyO3 و maturin

```text
$ uv venv && uv pip install maturin
$ maturin develop --release
```

کرِیت `pyo3 = "=0.30.1"`، `crate-type = ["cdylib"]` و یک `#[pymodule]` دارد. نوع‌ها و خطاها را خودش مدیریت می‌کند:

```rust
#[pyfunction]
fn count_multiples(n: i64) -> PyResult<u64> {
    if n < 0 { return Err(PyValueError::new_err("n must be >= 0")); }
    Ok((0..n).filter(|i| i % 3 == 0 || i % 5 == 0).count() as u64)
}
```

یک `#[pyclass] Counter` با `#[new]`، `incr` و فیلد فقط‌خواندنی `value` دمو را کامل می‌کند. build اینجا ۸ ثانیه طول کشید. از Python:

```text
correct on 5 sizes; count_multiples(10) = 5
ValueError: n must be >= 0
TypeError: 'str' object cannot be interpreted as an integer
15 15
ValueError: overflow
AttributeError: attribute 'value' of 'builtins.Counter' objects is not writable
```

خط اول نتیجه را برای پنج مقدار `n` با نسخه‌ی Python خالص مقایسه می‌کند. نوع غلط آرگومان قبل از اجرای کد شما `TypeError` می‌شود و `Err(PyValueError)` به exception معمولی تبدیل می‌شود. طبق مستندات PyO3، panic در Rust هم به exception در Python تبدیل می‌شود (اینجا اجرایش نکردم).

## رها کردن GIL

تابع Rust که {{< term "gil" "GIL" >}} را نگه دارد، ترد‌های دیگر Python را بلاک می‌کند. در PyO3 نسخه‌ی 0.30.1 متد `py.detach(|| ...)` است؛ بررسی کردم که کامپایل می‌شود و نام قدیمی `allow_threads` در `marker.rs` این نسخه نیست. `count_multiples_nogil` را با آن نوشتم. آزمایش ticker-thread من برای نشان دادن اثرش ایراد داشت (کامپایلر می‌تواند آن حلقه را ساده کند)، پس ادعای تسریع نمی‌کنم. سرعت Python در برابر Rust: اندازه‌گیری نشد.

## نوع‌ها، wheel و abi3

یک stub به نام `_core.pyi` و یک فایل خالی `py.typed` بدهید تا mypy {{< term "type-hint" "type hint" >}}ها را ببیند ([Type hint و mypy](/fa/posts/py-type-hints-mypy/)). `maturin build --release` یک {{< term "wheel" "wheel" >}} به نام `fastcount-0.1.0-cp314-cp314-macosx_11_0_arm64.whl` ساخت که فقط روی همان Python کار می‌کند. با feature به نام `abi3-py310` فایل `fastcount-0.1.0-cp310-abi3-macosx_11_0_arm64.whl` ساخته شد که طبق مستندات PyO3 ABI پایدار را برای Python 3.10 به بعد هدف می‌گیرد. فقط در Python 3.14 نصبش کردم و import را چک کردم؛ نسخه‌های دیگر را اجرا نکردم. داخل wheel فایل `_core.abi3.so` بود، حتی در macOS. برای انتشار: [بسته‌بندی و انتشار](/fa/posts/py-packaging-publishing/).

## چه وقت FFI نه (نظر من)

- هر فراخوانی سربار دارد و آرگومان‌ها را تبدیل می‌کند؛ فراخوانی‌های ریز و زیاد ممکن است از Python ساده هم بدتر شوند. کل بافر را بدهید.
- crash در کد native traceback پایتونی ندارد و debug سخت‌تر است.
- جایگزین‌ها: `cffi`، Cython و pybind11 (برای C++). برای Rust من سراغ PyO3 می‌روم.

## چند نکته‌ی مهم

- برای هر تابع ctypes هم `argtypes` و هم `restype` را تنظیم کنید.
- حافظه را با allocatorی آزاد کنید که ساخته است.
- هرگز اجازه ندهید panic از `extern "C"` رد شود.
- PyO3 را pin کنید و changelog را بخوانید؛ نام‌هایی مثل `detach` بین نسخه‌ها عوض شده‌اند.

## تمرین

تابع `reverse(data: bytes) -> bytes` را به کرِیت PyO3 اضافه کنید و تستی بنویسید که با `data[::-1]` مقایسه‌اش کند.

## قدم بعدی

سری Python اینجا تمام می‌شود. در ادامه سراغ سری سیستم‌های توزیع‌شده یا مهندسی نرم‌افزار بروید.
