+++
title = "musl"
fa_title = "musl"
summary = "کتابخانه‌ی استاندارد C کوچکی که به Rust اجازه می‌دهد باینری کاملاً ایستا برای Linux بسازد (targetهایی که اسمشان با -musl تمام می‌شود)، بی‌وابستگی به libc سیستم."
category = "Rust"
related = ["multi-stage-build"]
posts = ["rust-docker-ci-release"]
+++

بیشتر برنامه‌های Linux هنگام اجرا از کتابخانه‌ی C سیستم (glibc) استفاده می‌کنند. باینری Rust که برای targetای مثل `...-linux-musl` ساخته شود به‌جای آن musl را داخل خودش link می‌کند، پس نتیجه یک فایل ایستاست که روی هر Linux با همان معماری CPU اجرا می‌شود، حتی داخل یک image تقریباً خالی. target را با `rustup target add aarch64-unknown-linux-musl` اضافه می‌کنید و `--target` را به `cargo build` می‌دهید.
