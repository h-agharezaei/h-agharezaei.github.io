+++
title = "Garbage collector"
summary = "بخشی از runtime که objectهایی را که دیگر به آن‌ها دسترسی نیست آزاد می‌کند."
category = "Node.js"
fa_title = "garbage collector"
related = ["memory-leak"]
posts = ["node-profiling-memory-shutdown"]
+++

V8 برای objectهای جوان scavenge کوتاه و برای نسل قدیمی mark-compact کندتر اجرا می‌کند؛ `--trace-gc` هرکدام را چاپ می‌کند.
