+++
title = "AddressSanitizer"
fa_title = "AddressSanitizer (ASan)"
summary = "بررسی‌گر زمان اجرا که کامپایلر اضافه می‌کند و دسترسی خارج از محدوده، use-after-free و double free را گزارش می‌دهد."
category = "Security"
related = ["memory-safety", "buffer-overflow", "fuzzing"]
posts = ["sec-memory-safety-c-vs-rust", "sec-fuzzing"]
+++

با `-fsanitize=address` کامپایل کنید؛ برنامه در اولین دسترسی بد متوقف می‌شود و گزارشی با نوع خطا و شماره‌ی خط می‌دهد. برنامه را کند می‌کند و برای تست و CI است، نه production. [فازینگ](/fa/glossary/fuzzing/) معمولاً با آن اجرا می‌شود.
