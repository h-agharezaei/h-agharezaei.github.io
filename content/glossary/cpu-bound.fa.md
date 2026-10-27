+++
title = "CPU-bound"
summary = "کاری که سرعتش را پردازنده تعیین می‌کند، مثل محاسبه‌ی اعداد اول، نه انتظار برای I/O."
category = "Engineering"
fa_title = "وابسته به CPU"
related = ["io-bound","event-loop"]
posts = ["node-vs-go-when-to-use"]
+++

کار **وابسته به CPU** تمام مدت یک هسته را مشغول نگه می‌دارد. روی [event loop](/fa/glossary/event-loop/) تک‌رشته‌ای همه‌ی درخواست‌های دیگر را متوقف می‌کند؛ راه‌حل معمول، هسته یا thread بیشتر است.
