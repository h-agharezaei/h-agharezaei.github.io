+++
title = "Memory safety"
fa_title = "امنیت حافظه (memory safety)"
summary = "تضمین زبان یا ابزار که برنامه نمی‌تواند حافظه‌ای را بخواند یا بنویسد که مال آن نیست."
category = "Security"
related = ["buffer-overflow", "use-after-free", "ownership"]
posts = ["sec-memory-safety-c-vs-rust", "sec-fuzzing"]
+++

کد memory-safe نمی‌تواند از انتهای آرایه بیرون برود، از حافظه‌ی آزادشده استفاده کند یا آن را دوبار آزاد کند. Rust در کد safe این را در زمان کامپایل تضمین می‌کند، Go و بیشتر زبان‌های مدیریت‌شده با بررسی زمان اجرا و garbage collector. C این کار را به برنامه‌نویس می‌سپارد. [سرریز بافر](/fa/glossary/buffer-overflow/) و [use-after-free](/fa/glossary/use-after-free/) را ببینید.
