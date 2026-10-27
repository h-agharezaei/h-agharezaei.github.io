+++
title = "Load shedding"
fa_title = "load shedding (دور ریختن بار)"
summary = "رد کردن زودهنگام بعضی درخواست‌ها تا بقیه به‌موقع سرویس بگیرند."
category = "Distributed"
related = ["bulkhead", "backpressure", "circuit-breaker"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

صف یا pool محدود وقتی پر شد به‌جای رشد بی‌پایان صف، 503 یا 429 برمی‌گرداند. برای کلاینت، یک رد سریع و صادقانه معمولاً بهتر از پاسخ کندی است که بعد از timeout می‌رسد.
