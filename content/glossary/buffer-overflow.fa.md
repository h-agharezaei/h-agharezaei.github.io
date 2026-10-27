+++
title = "Buffer overflow"
fa_title = "سرریز بافر (buffer overflow)"
summary = "نوشتن (یا خواندن) بعد از انتهای یک بافر با اندازه‌ی ثابت که حافظه‌ی همسایه را خراب می‌کند."
category = "Security"
related = ["memory-safety", "use-after-free"]
posts = ["sec-memory-safety-c-vs-rust"]
+++

در C آرایه‌ی `char buf[8]` بررسی طول ندارد: `memset(buf, 'A', 10)` بی‌اعتراض دو بایت بعد از انتها می‌نویسد. روی stack اسمش stack-buffer-overflow است. راه‌حل: اندازه‌ی واقعی را پاس بدهید، از نوع‌های bounds-checked استفاده کنید و تست‌ها را با [AddressSanitizer](/fa/glossary/addresssanitizer/) اجرا کنید.
