+++
date = '2027-02-24T10:00:00+03:30'
draft = false
title = 'صدا زدن Rust از Go با FFI'
description = 'یک کتاب‌خانه‌ی static با Rust می‌سازیم، با cgo به برنامه‌ی Go لینک می‌کنیم و رشته، byte slice، struct، panic و ownership را در مرز دو زبان بررسی می‌کنیم.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "ffi", "cgo", "interop", "intermediate"]
cover = { image = "/images/covers/go-calls-rust-ffi.fa.png", alt = "صدا زدن Rust از Go با FFI", hiddenInSingle = true }
+++

[مقاله‌ی قبلی این سری](/fa/posts/go-rust-grpc-interop/) Go و Rust را از راه شبکه و با gRPC به هم وصل کرد. این مقاله راه درون‌پردازه‌ای است: یک باینری، Rust که به‌شکل کتاب‌خانه کامپایل شده، و Go که آن را از طریق **C ABI** و با **cgo** صدا می‌زند. کتاب‌خانه همان crate به نام `ffi-lib` از [مقاله‌ی Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) است که `add`، `greet`، `free_string`، `checksum`، `point_length` و `point_scale` را پشت هدر دست‌نویس `ffi_lib.h` export می‌کند. آن را بدون تغییر برداشتم. درباره‌ی pointerها: [مقاله‌ی pointerها](/fa/posts/go-pointers-memory/).

> Go 1.26، Rust 1.90، macOS (arm64)، `CGO_ENABLED=1` و `cc` سیستم. همه‌چیز به‌صورت محلی اجرا شده است.

## اول سمت Rust را بسازید

```text
$ cargo build --release
$ ls -l target/release | grep ffi_lib
-rw-r--r--  16577808  libffi_lib.a
-rwxr-xr-x    366704  libffi_lib.dylib
```

`libffi_lib.a` و `ffi_lib.h` را در پکیج Go به نام `ffi/` کپی کردم .

## پکیج Go

کامنت بالای `import "C"` کد C و دستورهای cgo است:

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

در `LDFLAGS` من به کتاب‌خانه‌ی اضافه‌ی مخصوص macOS نیازی نشد؛ خط لینک نشان می‌دهد cgo خودش `-framework CoreFoundation -lresolv` را اضافه می‌کند. نوع‌های C هیچ‌وقت خودکار تبدیل نمی‌شوند، پس هر آرگومان را می‌پیچیم (`C.int32_t`) و نتیجه را برمی‌گردانیم.

## رشته‌ها و ownership

رشته‌ی Go با NUL تمام نمی‌شود، برای همین `C.CString` آن را در حافظه‌ی C که با `malloc` گرفته شده کپی می‌کند. آزاد کردنش با `C.free` به عهده‌ی شماست. اما `greet` حافظه‌ی نوع دیگری برمی‌گرداند: حافظه‌ای که **allocator خود Rust** گرفته است.

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

قانون: حافظه را باید همان allocator‌ای آزاد کند که ساخته است. `C.free` روی pointer Rust (یا `free_string` روی یک `CString`) رفتار تعریف‌نشده (UB) است، برای همین اجرایش نکردم. `C.GoString` کپی می‌کند، پس رشته‌ی Go بعد از `free_string` معتبر می‌ماند.

## byte slice

```go
func Checksum(data []byte) uint64 {
	if len(data) == 0 { // &data[0] would panic
		return uint64(C.checksum(nil, 0))
	}
	return uint64(C.checksum((*C.uint8_t)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}
```

`&data[0]` بدون کپی، pointer به حافظه‌ی Go را به C می‌دهد. نتیجه را در `main` دمو با پیاده‌سازی FNV-1a در خود Go مقایسه کردم:

```text
add(2, 40) = 42
greet: Hello, Roham! <nil>
checksum("hello") rust=11831194018420276491 go=11831194018420276491 same=true
checksum("") rust=14695981039346656037 go=14695981039346656037 same=true
length = 5
scaled = {6 8}
```

دو خط آخر رفت‌وبرگشت struct از نوع `#[repr(C)]` است: `Length` یک `C.Point` را by value می‌دهد و `Scale` struct Go را در یک struct C کپی می‌کند و آدرسش را به `point_scale` می‌دهد.

## قواعد pointer در cgo

خلاصه: pointer Go فقط وقتی به C داده می‌شود که حافظه‌ای که به آن اشاره می‌کند خودش pointer Go نداشته باشد، و C نباید بعد از برگشتن تابع آن را نگه دارد. runtime این را به‌طور پیش‌فرض چک می‌کند (`GODEBUG=cgocheck=1`). عمداً با یک struct که `*int` دارد قانون را شکستم:

```go
type holder struct{ p *int }

n := 42
h := &holder{p: &n}
C.take(unsafe.Pointer(h)) // static void take(void *p) {}
```

```text
panic: runtime error: argument of cgo function has Go pointer to unpinned Go pointer
```

`go vet` روی این برنامه چیزی نگفت؛ چک در زمان اجرا انجام می‌شود. برای همین `Scale` یک کپی C پاس می‌دهد.

## وقتی Rust panic می‌کند

panic نمی‌تواند از یک تابع `extern "C"` بیرون بیاید و پردازه abort می‌شود. در کپی خودم از crate، تابع `ffi_test_panic` را پشت feature به نام `test-panic` اضافه کردم (نسخه‌ی اصلی دست‌نخورده است) و از Go صدایش زدم:

```text
calling Rust that panics
thread '<unnamed>' panicked at src/lib.rs:95:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
SIGABRT: abort
```

با `GOTRACEBACK=crash` کد خروج 134 بود؛ به‌صورت پیش‌فرض crash handler خود Go با کد 2 خارج شد. در هر دو حالت پردازه می‌میرد، پس تابع‌های export‌شده باید `catch_unwind` بگذارند و مقدار خطا برگردانند، مثل `greet`.

## checkout تمیز، static یا dynamic

ترتیب ثابت است: `cargo build --release`، کپی artifactها، بعد `go build`. بدون archive لینک با `ld: library 'ffi_lib' not found` شکست می‌خورد. با فایل `.a` باینری Go به کتاب‌خانه‌ی Rust وابسته نیست:

```text
$ otool -L ffidemo
  CoreFoundation.framework/.../CoreFoundation
  /usr/lib/libresolv.9.dylib
  /usr/lib/libSystem.B.dylib
```

اگر به‌جای آن با `.dylib` بسازید، یک خط برای `libffi_lib.dylib` اضافه می‌شود که به‌صورت مسیر مطلق به پوشه‌ی build در Cargo ثبت شده، پس برای deploy باید آن را درست کنید. cross-compile به toolchain کراس C نیاز دارد؛ فقط اشاره می‌کنم.

## هزینه‌ی مرز

load ماشین بالای 3 بود، پس benchmark نگرفتم و عددی نمی‌دهم. به‌صورت کیفی، صدا زدن با cgo گران‌تر از صدا زدن تابع Go است (مستندات Go هم همین را می‌گوید) و کامپایلر نمی‌تواند inline کند. کم و درشت صدا بزنید: یک فراخوانی با بافر بزرگ، نه یک میلیون فراخوانی ریز.

## FFI، gRPC یا wasm؟

- **FFI**: یک پردازه و بدون serialize، ولی `unsafe`، ownership دستی، toolchain C و abort در Rust سرویس Go شما را می‌کشد.
- **gRPC**: پردازه‌های جدا، قرارداد typed، deploy مستقل. هزینه‌اش یک hop شبکه و encoding است.
- **wasm**: guest در sandbox است و حافظه‌ی خطی خودش را دارد، پس داده کپی می‌شود و یک runtime لازم است.

## چند نکته

- حافظه را با allocator سازنده‌اش آزاد کنید: `C.free` برای `CString`، `free_string` برای `greet`.
- بعد از فراخوانی pointer Go را در C نگه ندارید و حافظه‌ی Go حاوی pointer Go را پاس ندهید.
- قبل از `&data[0]` slice خالی را چک کنید.
- panic در تابع صدا‌زده‌شده کل پردازه را abort می‌کند.

## تمرین

۱. C یک `CString` را فقط تا اولین بایت NUL می‌خواند. کاری کنید `Greet` برای نامی که `\x00` دارد خطا برگرداند (با `strings.IndexByte`) و تستش کنید.
۲. تابع `reverse_in_place` را به crate Rust اضافه کنید (تمرین مقاله‌ی قبلی Rust) و در Go بپیچید.

## قدم بعدی

بعدی: Futures، Pin و درون async در Rust.
