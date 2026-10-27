+++
title = "Retry budget"
summary = "سقفی برای retry‌ها به‌صورت کسری از درخواست‌های عادی، معمولاً با token bucket."
category = "Distributed"
fa_title = "بودجه‌ی retry"
related = ["retry-storm", "exponential-backoff"]
posts = ["ds-timeouts-retries-backoff", "ds-fault-injection-testing"]
+++

هر درخواست کسری از یک توکن (مثلاً ۰٫۱) اضافه می‌کند و هر retry یک توکن خرج می‌کند؛ پس retry‌ها حدود ۱۰٪ ترافیک می‌مانند. وقتی بودجه تمام شود کلاینت به‌جای فشار آوردن به سرور در حال دست‌وپا زدن، سریع شکست می‌خورد.
