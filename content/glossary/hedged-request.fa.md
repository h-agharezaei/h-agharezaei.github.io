+++
title = "Hedged request"
summary = "ارسال نسخه‌ی دوم یک درخواست کند به replica دیگر و استفاده از اولین پاسخ."
category = "Distributed"
fa_title = "درخواست hedged"
related = ["retry-budget", "idempotency"]
posts = ["ds-timeouts-retries-backoff"]
+++

کلاینت زمان کوتاهی (نزدیک تأخیر معمول) صبر می‌کند و همان درخواست را جای دیگری می‌فرستد. موارد کند را کم می‌کند، به قیمت کمی بار اضافه، و عملیات باید اجرای دوباره را تحمل کند ([idempotency](/fa/glossary/idempotency/)).
