+++
title = "Data race"
fa_title = "data race"
summary = "دو thread که هم‌زمان به یک حافظه دست می‌زنند، دست‌کم یکی با نوشتن، بدون هماهنگی."
category = "Rust"
related = ["send-and-sync", "rust-mutex", "os-thread"]
posts = ["rust-concurrency-threads"]
+++

مثال: دو thread هر کدام `counter += 1` را اجرا می‌کنند. هر کدام مقدار قدیمی را می‌خواند، یکی اضافه می‌کند و می‌نویسد؛ اگر هر دو یک مقدار قدیمی را خوانده باشند، یکی از افزایش‌ها گم می‌شود. Rust امن با ownership و trait‌های `Send` و `Sync` data race را در زمان کامپایل ممنوع می‌کند.
