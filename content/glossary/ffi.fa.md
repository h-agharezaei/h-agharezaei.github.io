+++
title = "FFI"
summary = "Foreign Function Interface: فراخوانی کدی که به زبان دیگری نوشته شده، معمولاً از راه C ABI."
category = "Go"
fa_title = "رابط توابع خارجی"
related = ["grpc"]
posts = ["go-calls-rust-ffi", "rust-unsafe-ffi"]
+++

Go از راه cgo و یک مرز سازگار با C به Rust می‌رسد؛ Rust توابع `extern "C"` را با `#[no_mangle]` منتشر می‌کند. عبور از این مرز هزینه دارد و مدیریت حافظه باید دقیق باشد: هر که بافر را اختصاص داده باید آزادش کند.
