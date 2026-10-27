+++
title = "Use-after-free"
fa_title = "استفاده پس از آزادسازی (use-after-free)"
summary = "استفاده از اشاره‌گری که حافظه‌ی مقصدش آزاد شده است."
category = "Security"
related = ["memory-safety", "buffer-overflow", "ownership"]
posts = ["sec-memory-safety-c-vs-rust"]
+++

بعد از `free(p)` اشاره‌گر هنوز آدرس قدیمی را دارد و خواندنش حتی ممکن است سالم به نظر برسد. در Rust قواعد [ownership](/fa/glossary/ownership/) و قرض‌گیری همین اشتباه را به خطای کامپایل تبدیل می‌کنند.
