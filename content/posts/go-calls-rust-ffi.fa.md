+++
date = '2027-02-24T10:00:00+03:30'
draft = false
title = 'صدا زدن Rust از Go با FFI'
description = 'یک کتاب‌خانه‌ی static با Rust می‌سازیم، با cgo به برنامه‌ی Go لینک می‌کنیم و رشته، byte slice، struct، panic و ownership را در مرز دو زبان بررسی می‌کنیم.'
contentType = 'tutorial'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "ffi", "cgo", "interop", "intermediate"]
cover = { image = "/images/covers/go-calls-rust-ffi.fa.png", alt = "صدا زدن Rust از Go با FFI", hiddenInSingle = true }
+++

یک سرویس Go دارید و یک تکه‌ی کوچک Rust که یک کار را عالی انجام می‌دهد، مثلاً یک checksum یا یک parser که نمی‌خواهید دوباره بنویسید. [نوشته‌ی قبل](/fa/posts/go-rust-grpc-interop/) این دو زبان را با gRPC به هم وصل کرد: دو برنامه، یک شبکه‌ی بینشان و یک قرارداد تایپ‌دار. این انتخاب پیش‌فرض خوبی است، ولی گاهی یک گام شبکه برای تابعی که یک میکروثانیه طول می‌کشد قیمت اشتباهی است. راه دیگر این است که کد Rust را به یک کتابخانه کامپایل کنیم و از Go، داخل همان پروسه، مثل یک فراخوانی تابع معمولی صدایش بزنیم.

یک گیر هست که کل طراحی را تعیین می‌کند: **Go و Rust قرارداد فراخوانی همدیگر را نمی‌شناسند، ولی هر دو زبانِ C را بلدند.** پس فراخوانی از Go به C و از C به Rust می‌رود. در Go ابزارش **cgo** است: به کد Go اجازه می‌دهد تابع‌های C را صدا بزند. در سمت Rust هم تابع‌ها را با قرارداد فراخوانی C صادر می‌کنیم ({{< term "ffi" "FFI" >}}، یعنی رابط فراخوانی تابع خارجی، روی {{< term "abi" "ABI" >}} زبان C). هرچه از این مرز رد شود C ساده است: عدد صحیح، اشاره‌گر و struct تخت. رشته، slice و ownership جزو آن نیستند و دست‌کاری‌شان با دست بیشتر این نوشته را می‌گیرد.

کتابخانه همان crate به نام `ffi-lib` از [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) است که `add`، `greet`، `free_string`، `checksum`، `point_length` و `point_scale` را پشت یک هدر C دست‌نویس به اسم `ffi_lib.h` صادر می‌کند. بدون تغییر از آن استفاده می‌کنم (تنها اضافه، یک تابع آزمایشی پشت یک feature در یک نسخه‌ی جدا است). در سمت Go، [نوشته‌ی اشاره‌گرها](/fa/posts/go-pointers-memory/) پیش‌زمینه‌ی مفیدی است.

> همه‌چیز را دوباره به‌صورت محلی با Go 1.27، Rust 1.90، macOS (arm64)، `CGO_ENABLED=1` و `cc` سیستم اجرا کردم. کتابخانه‌ی Rust برای این اجرا از روی کد crate دوباره ساخته شد.

## چه بهایی از همان اول می‌دهید

بهای راه درون‌پروسه‌ای این است که دو دنیا سرنوشت مشترک پیدا می‌کنند: **panic در Rust، داخل تابعی که Go صدایش زده، کل پروسه را می‌کشد.** آن را آخر نوشته نشان می‌دهم. تا آن‌جا در ذهن داشته باشید.

## اول سمت Rust را بسازید

```text
$ cargo build --release
$ ls -l target/release | grep ffi_lib
-rw-r--r--  16577808  libffi_lib.a
-rwxr-xr-x    366704  libffi_lib.dylib
```

crate طوری تنظیم شده که دو نوع کتابخانه بسازد. `libffi_lib.a` یک **کتابخانه‌ی ایستا** است: آرشیوی از کد کامپایل‌شده که linker آن را داخل باینری نهایی کپی می‌کند. `libffi_lib.dylib` یک **کتابخانه‌ی پویا** است که برنامه هنگام شروع بارگذاری‌اش می‌کند (روی Linux پسوندش `.so` است). `libffi_lib.a` و `ffi_lib.h` را در یک پکیج Go به نام `ffi/` گذاشتم (هدر کنار فایل Go و کتابخانه در `ffi/lib/`).

## پکیج Go

در فایل Go که از cgo استفاده می‌کند، کامنتِ درست بالای `import "C"` کامنت نیست: کد C و دستورهای cgo است. این بخش اول `ffi/ffi.go` است:

```go
/*
#cgo LDFLAGS: -L${SRCDIR}/lib -lffi_lib
#include <stdlib.h>
#include "ffi_lib.h"
*/
import "C"

func Add(a, b int32) int32 {
	return int32(C.add(C.int32_t(a), C.int32_t(b)))
}
```

بخوانیمش: `#cgo LDFLAGS` به linker می‌گوید کتابخانه کجاست (`-L`، نسبت به پوشه‌ی کد) و اسمش چیست (`-lffi_lib` یعنی `libffi_lib`). خط‌های `#include` اعلان‌ها را می‌آورند تا Go بداند `C.add` چیست. بعد از آن، تابع‌ها و تایپ‌های C در Go با پیشوند `C.` دیده می‌شوند.

تایپ‌های C هیچ‌وقت خودکار تبدیل نمی‌شوند. `int32` در Go با `C.int32_t` یکی نیست، هرچند شبیه‌اند، پس هر آرگومان را می‌پیچیم (`C.int32_t(a)`) و هر نتیجه را برمی‌گردانیم. پرحرف است، ولی هر عبور از مرز را دیدنی می‌کند.

## رشته‌ها و ownership

دو واقعیت درباره‌ی رشته‌ها این‌جا را جای اشتباه می‌کند. اول، رشته‌ی Go یک اشاره‌گر و یک طول است و NUL در انتها ندارد، در حالی که C آرایه‌ای با پایان NUL انتظار دارد. پس `C.CString` از رشته‌ی Go یک نسخه در حافظه‌ی C می‌سازد که با `malloc` گرفته شده، و آزادکردنش با `C.free` به عهده‌ی شماست. دوم، `greet` رشته‌ای برمی‌گرداند که Rust گرفته است، با **تخصیص‌دهنده‌ی Rust**. این حافظه‌ی دیگری با صاحب دیگری است.

```go
func Greet(name string) (string, error) {
	cs := C.CString(name)
	defer C.free(unsafe.Pointer(cs)) // malloc'd by C: free with C.free

	g := C.greet(cs) // allocated by Rust
	if g == nil {
		return "", errors.New("greet failed")
	}
	defer C.free_string(g) // back to Rust, never C.free
	return C.GoString(g), nil // copies into Go memory
}
```

قاعده: **حافظه را همان تخصیص‌دهنده‌ای آزاد کند که ساخته است.** `C.free` روی اشاره‌گر Rust، یا `free_string` روی اشاره‌گر `C.CString`، {{< term "undefined-behavior" "رفتار تعریف‌نشده" >}} است: ممکن است crash کند یا حافظه را خراب کند یا از شانس کار کند. عمداً اجرایش نکردم. به همین دلیل هم کتابخانه‌ی Rust تابع `free_string` دارد: تنها کدی که می‌تواند رشته‌ی Rust را با امنیت آزاد کند خود Rust است.

`C.GoString` رشته‌ی C را در حافظه‌ی Go کپی می‌کند. بعد از آن رشته‌ی Go مستقل است و به همین دلیل می‌شود بلافاصله `free_string` را صدا زد (`defer` بعد از ارزیابی عبارت `return` اجرا می‌شود).

## slice بایت

دادن slice ساده‌تر است: C فقط یک اشاره‌گر به بایت اول و یک طول لازم دارد.

```go
func Checksum(data []byte) uint64 {
	if len(data) == 0 { // &data[0] would panic
		return uint64(C.checksum(nil, 0))
	}
	return uint64(C.checksum((*C.uint8_t)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}
```

`&data[0]` اشاره‌گری مستقیم به حافظه‌ی Go به C می‌دهد، بدون کپی. slice خالی عنصر اول ندارد، پس شاخه‌ی جدا می‌خواهد.

برای دیدن اینکه دو زبان واقعاً هم‌نظرند، برنامه‌ی دمو همان checksum را با یک پیاده‌سازی کوچک FNV-1a در Go هم حساب می‌کند و مقایسه می‌کند. این خروجی واقعی `go run ./cmd/demo` است:

```text
add(2, 40) = 42
greet: Hello, Roham! <nil>
checksum("hello") rust=11831194018420276491 go=11831194018420276491 same=true
checksum("") rust=14695981039346656037 go=14695981039346656037 same=true
length = 5
scaled = {6 8}
```

دو خط اول فراخوانی ساده و رفت‌وبرگشت رشته است. دو خط `checksum` نشان می‌دهند Rust و Go هم برای ورودی معمولی و هم برای ورودی خالی همان عدد ۶۴ بیتی را حساب می‌کنند. دو خط آخر رفت‌وبرگشت یک struct با `#[repr(C)]` است: `Length` یک `C.Point` را با مقدار می‌دهد، پس `Point{3, 4}` طول ۵ دارد، و `Scale` struct گو را در یک struct C کپی می‌کند و آدرسش را به `point_scale` می‌دهد که آن را در جا دو برابر می‌کند.

## قاعده‌های اشاره‌گر در cgo

دادن اشاره‌گر به C قاعده دارد، چون garbage collector گو می‌تواند حافظه‌ی Go را جابه‌جا و آزاد کند و C از آن خبر ندارد. خلاصه: اشاره‌گر Go را فقط وقتی می‌شود به C داد که حافظه‌ای که به آن اشاره می‌کند خودش اشاره‌گر Go نداشته باشد، و C نباید اشاره‌گر را بعد از برگشت فراخوانی نگه دارد. runtime بخش اول را به‌طور پیش‌فرض بررسی می‌کند (`GODEBUG=cgocheck=1`، طبق مستندات cgo).

عمداً قاعده را شکستم: structی که یک `*int` دارد را به یک تابع C خالی دادم:

```go
type holder struct{ p *int }

n := 42
h := &holder{p: &n}
C.take(unsafe.Pointer(h)) // static void take(void *p) {}
```

```text
panic: runtime error: argument of cgo function has Go pointer to unpinned Go pointer
```

`go vet` ایرادی در این برنامه نیافت؛ پس بررسی هنگام اجرا انجام می‌شود، و فقط اگر آن مسیر کد اجرا شود. به همین دلیل `Scale` در بالا `&p` را مستقیم نمی‌دهد: یک نسخه‌ی C از struct می‌سازد و آدرس همان را می‌دهد.

## وقتی Rust panic می‌کند

panic در Rust معمولاً stack را باز می‌کند (unwind)، ولی نباید از میان یک تابع `extern "C"` به کد خارجی برسد. Rust در این حالت به‌جایش abort می‌کند. برای دیدن اینکه این برای یک برنامه‌ی Go چه معنایی دارد، تابعی به اسم `ffi_test_panic` اضافه کردم که فقط `panic!("boom from Rust")` را اجرا می‌کند. پشت یک feature به اسم `test-panic` در یک نسخه‌ی جدا از crate است (اصل دست‌نخورده است). Go صدایش زد و این شد (خط‌های backtrace مربوط به Rust حذف شده‌اند):

```text
calling Rust that panics
thread '<unnamed>' panicked at src/lib.rs:95:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
SIGABRT: abort
```

برنامه‌ی Go هرگز به خط بعدی‌اش نرسید. با `GOTRACEBACK=crash` کد خروج ۱۳۴ بود (پروسه با SIGABRT کشته شد)؛ به‌طور پیش‌فرض crash handler گو با کد ۲ خارج شد. در هر دو حالت کل پروسه رفته است. پس یک تابع صادرشده‌ی Rust نباید اجازه بدهد panic بیرون بزند: بدنه را در `catch_unwind` بپیچید و یک مقدار خطا برگردانید، همان‌طور که `greet` می‌کند (در شکست NULL برمی‌گرداند و برای همین سمت Go بررسی `g == nil` دارد).

## چک‌اوت تمیز، ایستا یا پویا

ترتیب کارها ثابت است: `cargo build --release`، کپی artifactها، بعد `go build`. اگر دو مرحله‌ی اول را فراموش کنید، لینک شکست می‌خورد، چون ابزار Go کتابخانه را نمی‌یابد:

```text
ld: library 'ffi_lib' not found
```

با فایل `.a`، باینری Go در زمان اجرا به کتابخانه‌ی Rust وابسته نیست، چون کد داخل خودش است. `otool -L` (معادل `ldd` در macOS) فقط کتابخانه‌های سیستمی را فهرست می‌کند:

```text
$ otool -L ffidemo
  /usr/lib/libresolv.9.dylib
  /usr/lib/libSystem.B.dylib
```

(شماره‌ی نسخه‌ی هر خط را حذف کرده‌ام. اجرای اصلی با Go 1.26 `CoreFoundation` را هم فهرست کرده بود؛ اجرای Go 1.27 نه.)

اگر به‌جای آن به `.dylib` لینک کنید، یک خط برای `libffi_lib.dylib` اضافه می‌شود و آدرسش به‌صورت مسیر مطلق داخل پوشه‌ی build کارگو ثبت می‌شود (در build من `.../target/release/deps/libffi_lib.dylib`). فرستادن چنین باینری‌ای به ماشین دیگر یعنی باید آن مسیر را درست کنید. cross-compile به toolchain متقاطع C نیاز دارد؛ فقط ذکرش می‌کنم و امتحان نکردم.

## هزینه‌ی مرز

ماشین حین اجراها مشغول بود (load average حدود ۴)، پس benchmark اجرا نکردم و عددی نمی‌دهم. آنچه کیفی می‌توانم بگویم: فراخوانی cgo گران‌تر از فراخوانی معمولی Go است (مستندات Go هم همین را می‌گویند) و کامپایلر نمی‌تواند آن را inline کند. پس **فراخوانی درشت** را ترجیح بدهید: یک فراخوانی با بافر بزرگ، نه یک میلیون فراخوانی با بافر ریز.

## FFI، gRPC یا wasm؟

- **{{< term "ffi" "FFI" >}}**: یک پروسه و بدون serialize. در عوض کد `unsafe`، ownership دستی، toolchain C در build و abort در Rust که سرویس Go شما را می‌کشد.
- **gRPC**: پروسه‌های جدا، قرارداد تایپ‌دار، deploy مستقل، و شکست یکی دیگری را نمی‌کشد. بهایش یک گام شبکه و encoding است.
- **wasm** (WebAssembly): کد مهمان در sandbox است و حافظه‌ی خودش را دارد، پس داده باید داخل و بیرون کپی شود و برای میزبانی‌اش runtime لازم دارید.

## جاهایی که مرز گاز می‌گیرد

- Rust را پیش از Go بسازید؛ build گو این کار را برایتان نمی‌کند.
- حافظه را با تخصیص‌دهنده‌ای آزاد کنید که ساخته است: `C.free` برای `C.CString` و `free_string` برای چیزی که `greet` برگرداند.
- اشاره‌گر Go را بعد از فراخوانی در C نگه ندارید و هرگز حافظه‌ی Goی حاوی اشاره‌گر Go را نفرستید.
- پیش از گرفتن `&data[0]` خالی‌بودن slice را بررسی کنید.
- panic در Rust داخل تابعی که Go صدا زده، کل پروسه را abort می‌کند.

## تمرین

۱. C یک `CString` را فقط تا اولین بایت NUL می‌خواند. کاری کنید `Greet` برای نام‌های حاوی `\x00` خطا برگرداند (از `strings.IndexByte` استفاده کنید) و تستش کنید.
۲. `reverse_in_place` را به crate Rust اضافه کنید (تمرین ۱ از [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/)) و در Go بپیچیدش.

## قدم بعدی

نوشته‌ی بعدی این سری «پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS» است. بعد از gRPC و FFI، پروژه‌ی پایانی سرویس‌های Go و Rust را از طریق رویدادهای NATS به هم وصل می‌کند.
