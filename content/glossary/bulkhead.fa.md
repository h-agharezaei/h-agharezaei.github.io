+++
title = "Bulkhead"
fa_title = "bulkhead (تیغه‌ی جداکننده)"
summary = "سقف منبع جداگانه برای هر وابستگی تا یک وابستگی کند نتواند همه‌چیز را مصرف کند."
category = "Distributed"
related = ["circuit-breaker", "semaphore", "load-shedding"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

نامش از محفظه‌های کشتی می‌آید. در کد معمولاً یک worker pool یا [semaphore](/fa/glossary/semaphore/) جدا برای هر وابستگی است تا خرابی یک بخش فقط محفظه‌ی خودش را پر کند.
