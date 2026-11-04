+++
date = '2027-05-24T10:00:00+03:30'
draft = false
title = 'صدا زدن Rust از Python با ctypes و PyO3'
description = 'صدا زدن Rust از Python با ctypes و PyO3: C ABI، آزاد کردن حافظه، panic، maturin، exception، رها کردن GIL، wheel با abi3 و زمان‌هایی که نباید.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "rust", "ffi", "ctypes", "pyo3", "maturin"]
cover = { image = "/images/covers/py-ffi-pyo3-ctypes.fa.png", alt = "صدا زدن Rust از Python با ctypes و PyO3", hiddenInSingle = true }
+++

فرض کنید در برنامه‌ی Python حلقه‌ای دارید که ساده‌اش این است که بیش از حد کند است: میلیون‌ها تکرار از حساب‌وکتاب ساده، و Python بیشتر وقتش را صرف اجرای مفسر می‌کند نه ریاضی شما. همین منطق را در Rust هم دارید، سریع و تست‌شده. آیا Python می‌تواند آن را صدا بزند؟

می‌تواند، با {{< term "ffi" "FFI" >}} (واسط فراخوانی تابع خارجی): راهی که یک زبان تابع‌های زبان دیگر را صدا بزند. بعد از [پردازش داده‌ی کوچک با csv و sqlite3](/fa/posts/py-data-csv-sqlite/)، این آخرین پست سری Python دو راه برای صدا زدن Rust را نشان می‌دهد. `ctypes` همراه Python می‌آید و در طرف Python مرحله‌ی ساخت لازم ندارد: کتابخانه‌ی کامپایل‌شده را بار می‌کنید و تابع‌هایش را صدا می‌زنید. راه دوم {{< term "pyo3" "PyO3" >}} با maturin است: از کد Rust یک ماژول واقعی Python می‌سازد، با نوع‌ها و exceptionهای Python.

اولین چیزی که می‌بینید یک هشدار است. بدون اعلام نوع، ctypes عدد ۵٬۰۰۰٬۰۰۰٬۰۰۰ یک تابع Rust را بی‌صدا به ۷۰۵٬۰۳۲٬۷۰۴ تبدیل می‌کند. مرز دو زبان جایی است که کامپایلر دیگر کمکتان نمی‌کند، پس این پست بیشتر درباره‌ی این است که چه چیزی از مرز رد می‌شود، مالکش کیست و چه چیزی خراب می‌شود. قاعده‌های مرز همان‌هایی است که در [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) و [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) آمده. thread در Python و قفلش در [GIL و threading](/fa/posts/py-gil-threading/) است.

> همه‌چیز را دوباره با Python 3.14.0، Rust 1.90، macOS arm64، {{< term "uv" "uv" >}} 0.10.9، maturin 1.15.0 و PyO3 با pin روی `=0.30.1` اجرا کردم، در نسخه‌های موقتی از دموها که بعد پاک کردم. نصب‌ها از cache آفلاین آمدند. ماشین شلوغ بود، پس **هیچ زمانی** منتشر نمی‌کنم. مسیرها را با `<tmp>` نشان می‌دهم؛ Rust هنگام abort در بخش ۱ یک stack backtrace هم چاپ می‌کند که حذفش کرده‌ام (۲۸ فریم آدرس که هر اجرا فرق می‌کند).

## بخش ۱: ctypes و {{< term "abi" "ABI" >}} زبان C

Python اصلاً چطور می‌تواند کتابخانه‌ی Rust را صدا بزند؟ از طریق ABI زبان C، یعنی قرارداد دودویی مشترک درباره‌ی اینکه تابع‌ها آرگومان را چطور بگیرند و نتیجه را چطور برگردانند. تقریباً هر زبانی آن را می‌فهمد، پس زمین مشترک است. در طرف Rust یک crate از نوع `cdylib` می‌سازید (کتابخانه‌ی پویا با رابط C) و هر تابع صادرشده را `extern "C"` و `#[no_mangle]` علامت می‌زنید، که نامش را برای بقیه خوانا نگه می‌دارد. دموی من پنج تابع صادر می‌کند که حالت‌های معمول را نشان می‌دهند:

- `add(i32, i32)`، عددهای ساده.
- `big() -> i64`، که ۵٬۰۰۰٬۰۰۰٬۰۰۰ برمی‌گرداند، عددی که در ۳۲ بیت جا نمی‌شود.
- `checksum(*const u8, usize)`، هش (FNV-1a) یک بافر بایت.
- `greet`، که رشته‌ای برمی‌گرداند که Rust روی heap ساخته، و `free_string` که آن را آزاد می‌کند.
- `each_square`، که به Python callback می‌زند.

در macOS کتابخانه `libdemo.dylib` است (در Linux `.so`). در Python آن را بار می‌کنید و **نوع هر تابع را اعلام می‌کنید**: چه می‌گیرد (`argtypes`) و چه برمی‌گرداند (`restype`):

```python
lib = ctypes.CDLL("<tmp>/libdemo.dylib")
lib.add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.add.restype = ctypes.c_int32
lib.checksum.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
lib.checksum.restype = ctypes.c_uint64
```

با این اعلام‌ها، صدا زدن `add` و `checksum` و مقایسه‌ی checksum با همان الگوریتم نوشته‌شده در Python این را می‌دهد:

```text
add(2, 40) = 42
checksum(b'hello') = 11831194018420276491
python fnv-1a      = 11831194018420276491
```

checksum در Rust و Python یکی است، پس بایت‌ها سالم از مرز رد شدند. حالا تله. کتابخانه فقط کد ماشین است و اطلاعات نوعی ندارد که Python بخواند. پس وقتی نوع اعلام نکنید ctypes حدس می‌زند، و حدسش `int` (۳۲ بیت) است. `big()` در واقع عدد صحیح ۶۴ بیتی برمی‌گرداند:

```text
big() with default restype: 705032704
big() with c_int64:         5000000000
```

۵٬۰۰۰٬۰۰۰٬۰۰۰ منهای 2^32 برابر ۷۰۵٬۰۳۲٬۷۰۴ است: بیت‌های بالا بی‌صدا بریده شدند. همین نبود اعلام باعث شد `add(1, 2, 3, 4)` با دو آرگومان اضافه و بدون خطا اجرا شود. هیچ‌چیز هشدار نمی‌دهد. پس برای هر تابع همیشه `argtypes` و `restype` را تنظیم کنید.

## رشته‌ها و مالکیت

عددها حالت آسان‌اند. رشته‌ها سخت‌ترند، چون رشته حافظه است و کسی باید آن را آزاد کند. `greet` نتیجه‌اش را داخل Rust و با allocator خود Rust می‌سازد. یعنی Python باید اشاره‌گر را به `free_string` در Rust برگرداند، نه به `free` زبان C: حافظه را باید همان allocatorی آزاد کند که ساخته است. این همان قاعده‌ی پست Go است.

در طرف Python یک تله هست. اگر `restype = ctypes.c_char_p` بنویسید، طبق مستندات ctypes، نتیجه به `bytes` پایتونی تبدیل می‌شود و اشاره‌گر اصلی از دست می‌رود، پس هرگز نمی‌توانید آزادش کنید. از `c_void_p` استفاده کنید تا اشاره‌گر خام بماند، متن را با `string_at` بخوانید و بعد آزاد کنید:

```python
lib.greet.restype = ctypes.c_void_p
p = lib.greet(b"Roham")
print(ctypes.string_at(p).decode())  # Hello, Roham!
lib.free_string(p)
```

دمو `greet: Hello, Roham!` چاپ کرد. callback جهت برعکس است: Rust یک تابع Python را صدا می‌زند. در ctypes آن را با `CFUNCTYPE` می‌پیچید و باید شیء callback را در تمام مدت فراخوانی زنده نگه دارید، چون اگر Python آن را جمع کند، Rust حافظه‌ی آزادشده را صدا می‌زند. `each_square(4, cb)` باعث شد Python این را ثبت کند: `[(0, 0), (1, 1), (2, 4), (3, 9)]`، یعنی اندیس و مربعش برای هر یک از ۴ گام.

## وقتی panic از مرز رد می‌شود

اگر کد Rust panic کند چه؟ panic معمولاً stack را باز می‌کند (unwind)، ولی آن‌طرف مرز C چیزی نیست که unwind در Rust را بفهمد. Rust مدرن به همین دلیل اجازه نمی‌دهد از تابع `extern "C"` بیرون unwind شود و abort می‌کند. تابعی به نام `boom()` را که فقط panic می‌کند در یک subprocess صدا زدم و کد خروج را دیدم:

```text
exit code -6
calling boom()

thread '<unnamed>' panicked at src/lib.rs:49:5:
boom from Rust
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread '<unnamed>' panicked at library/core/src/panicking.rs:225:5:
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

`-6` روش Python برای گفتن «با سیگنال ۶ کشته شد» است، یعنی SIGABRT. کل process پایتون همان‌جا مرد، بدون exception و بدون چیزی که با `except` بگیرید. پس قاعده این است که panic هرگز نباید از تابع `extern "C"` بیرون برود. راه‌حل `catch_unwind` داخل خود تابع Rust است، که panic را به مقدار خطایی تبدیل می‌کند که صدازننده بررسی کند، مثل `-1` یا اشاره‌گر null. `boom_safe()` من همین کار را می‌کند و `-1` برگرداند. (Rust پیام panic را باز هم روی stderr چاپ می‌کند، ولی process زنده می‌ماند.)

## بخش ۲: PyO3 و maturin

ctypes با هر کتابخانه‌ای کار می‌کند ولی همه‌ی جزئیات را به دوش شما می‌گذارد. PyO3 برعکس است: تابع‌های Rust را مثل Rust می‌نویسید و PyO3 یک ماژول واقعی Python می‌سازد، با تبدیل آرگومان و exception. **maturin** ابزار ساختی است که crate را کامپایل می‌کند و در محیط شما نصب می‌کند:

```text
$ uv venv && uv pip install maturin
$ maturin develop --release
```

crate مقدار `pyo3 = "=0.30.1"` (pin‌شده، چون API بین نسخه‌ها عوض می‌شود)، `crate-type = ["cdylib"]` و یک `#[pymodule]` دارد. با `#[pyfunction]` تابع از Python قابل صدا زدن می‌شود. نوع‌ها و خطاها را خود PyO3 مدیریت می‌کند:

```rust
#[pyfunction]
fn count_multiples(n: i64) -> PyResult<u64> {
    if n < 0 { return Err(PyValueError::new_err("n must be >= 0")); }
    Ok((0..n).filter(|i| i % 3 == 0 || i % 5 == 0).count() as u64)
}
```

این تابع عددهای کوچک‌تر از `n` را می‌شمارد که بر ۳ یا ۵ بخش‌پذیرند. یک `#[pyclass] Counter` با `#[new]`، متد `incr` و فیلد فقط‌خواندنی `value` دمو را کامل می‌کند. این خروجی `check.py` است که ماژول را از Python به کار می‌برد (اولین build خود PyO3 را هم کامپایل می‌کند، پس طول می‌کشد):

```text
correct on 5 sizes; count_multiples(10) = 5
ValueError: n must be >= 0
TypeError: 'str' object cannot be interpreted as an integer
15 15
ValueError: overflow
AttributeError: attribute 'value' of 'builtins.Counter' objects is not writable
```

خط به خط:

- خط اول تابع Rust را برای پنج مقدار `n` با نسخه‌ی خالص Python مقایسه می‌کند، و بعد `count_multiples(10) = 5` را نشان می‌دهد (عددهای ۰، ۳، ۵، ۶ و ۹).
- `Err(PyValueError)` در Rust برای `-1` به `ValueError` معمولی Python تبدیل شد.
- دادن رشته‌ی `"x"` پیش از اجرای کد Rust به `TypeError` تبدیل شد: PyO3 آرگومان را تبدیل می‌کند و نوع غلط را رد می‌کند.
- `Counter(10).incr(5)` عدد ۱۵ را برگرداند و `value` هم ۱۵ خواند.
- `Counter(2**64 - 1).incr(1)` از `u64` سرریز کرد و `checked_add` آن را به‌جای wrap شدن به `ValueError: overflow` تبدیل کرد.
- انتساب به `value` با `AttributeError` شکست خورد، چون فیلد فقط‌خواندنی تعریف شده بود (`get` ولی نه `set`).

طبق مستندات PyO3، panic در Rust هم به exception در Python تبدیل می‌شود؛ اینجا یکی را راه نینداختم.

## آزاد کردن GIL

Python یک قفل سراسری دارد، {{< term "gil" "GIL" >}}، و تا وقتی thread کد Python اجرا می‌کند آن را نگه می‌دارد و بقیه‌ی threadهای Python منتظر می‌مانند. تابع Rust که از Python صدا زده می‌شود قفل را نگه می‌دارد مگر اینکه رهایش کند، پس threadهای دیگر Python را بلاک می‌کند، با اینکه به آن‌ها نیازی ندارد. PyO3 اجازه می‌دهد کد Rust هنگام کار قفل را رها کند. در PyO3 0.30.1 متدش `py.detach(|| ...)` است. `count_multiples_nogil` را با آن نوشتم، و بررسی کردم که کامپایل می‌شود و نام قدیمی `allow_threads` در `marker.rs` این نسخه نیست (نام بین نسخه‌ها عوض شده، برای همین pin اهمیت دارد). آزمایش من برای دیدن اثرش با یک thread تیک‌زن ایراد داشت، چون کامپایلر می‌تواند آن حلقه را حذف کند، پس ادعای افزایش سرعتی نمی‌کنم.

## نوع‌ها، wheel و abi3

برای اینکه طرف Python نوع‌ها را بشناسد، یک فایل stub به نام `_core.pyi` و یک `py.typed` خالی همراه بسته کنید تا mypy {{< term "type-hint" "type hint" >}}‌ها را ببیند ([type hint و mypy](/fa/posts/py-type-hints-mypy/)). بعد {{< term "wheel" "wheel" >}} می‌سازید. wheel با کد کامپایل‌شده به یک سکو و به‌طور پیش‌فرض به یک نسخه‌ی Python بسته است. `maturin build --release` بدون هیچ feature ویژه این را داد:

```text
fastcount-0.1.0-cp314-cp314-macosx_11_0_arm64.whl
```

نام را بخوانید: `cp314` یعنی CPython 3.14، پس این wheel فقط روی همان Python و روی macOS arm64 کار می‌کند. روشن کردن feature به نام `abi3-py310` در `Cargo.toml` (مثل دمو) نام دیگری داد:

```text
fastcount-0.1.0-cp310-abi3-macosx_11_0_arm64.whl
```

طبق مستندات PyO3، `abi3` ABI پایدار Python را هدف می‌گیرد، پس یک wheel برای Python 3.10 به بعد کار می‌کند. آن را در یک محیط تازه‌ی Python 3.14 نصب کردم و دیدم `import fastcount` کار می‌کند و `count_multiples(10)` عدد ۵ برمی‌گرداند؛ نسخه‌های دیگر Python را اجرا نکردم. wheel شامل `_core.abi3.so` است (حتی در macOS)، در برابر `_core.cpython-314-darwin.so` در نسخه‌ی مخصوص یک نسخه. فایل‌های بسته در هر دو `fastcount/__init__.py`، `_core.pyi` و `py.typed` هستند. (فهرست اولیه‌ی من یک فایل سرگردان `__pycache__` هم داشت که از اجراهای قبلی مانده بود و اینجا نیاوردمش.) برای انتشار [بسته‌بندی و انتشار پروژه‌ی Python](/fa/posts/py-packaging-publishing/) و برای محیط‌ها [محیط Python: venv و uv](/fa/posts/py-environment-uv-venv/) را ببینید.

## وقتی از FFI استفاده نکنید (نظر خودم)

- هر فراخوانی سربار دارد و آرگومان‌ها را تبدیل می‌کند، پس فراخوانی‌های ریز و زیاد می‌توانند از Python ساده بازنده شوند. کل بافر را بدهید و بگذارید Rust در هر فراخوانی کار زیادی بکند.
- خرابی در کد native traceback پایتونی ندارد و دیباگ سخت‌تر است. SIGABRT بالا را یادتان باشد.
- جایگزین‌ها هست: `cffi`، Cython و pybind11 (برای C++). برای Rust خودم سراغ PyO3 می‌روم.

## قاعده‌های مرز FFI

- برای هر تابع ctypes هم `argtypes` و هم `restype` را تنظیم کنید، وگرنه بریده‌شدن بی‌صدا را بپذیرید.
- حافظه را با allocatorی آزاد کنید که ساخته است، و اشاره‌گری را که باید آزاد کنید هرگز به یک نسخه‌ی کپی‌شده تبدیل نکنید.
- هرگز اجازه ندهید panic از `extern "C"` رد شود؛ بگیریدش و مقدار خطا برگردانید.
- PyO3 را pin کنید و changelog را بخوانید؛ نام‌هایی مثل `detach` بین نسخه‌ها عوض شده‌اند.

## تمرین

تابع `reverse(data: bytes) -> bytes` را به crate مربوط به PyO3 اضافه کنید و تستی بنویسید که با `data[::-1]` مقایسه‌اش کند.

## قدم بعدی

سری Python اینجا تمام می‌شود. در ادامه سراغ سری سیستم‌های توزیع‌شده یا مهندسی نرم‌افزار بروید.
