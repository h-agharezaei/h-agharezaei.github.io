+++
title = "Circuit breaker"
fa_title = "circuit breaker (قطع‌کننده‌ی مدار)"
summary = "wrapper‌ای که چند وقت صدا زدن وابستگی خراب را متوقف می‌کند و به‌جایش سریع شکست می‌دهد."
category = "Distributed"
related = ["bulkhead", "load-shedding", "cascading-failure"]
posts = ["ds-circuit-breaker-bulkhead", "eng-postmortems-blameless"]
+++

یک state machine کوچک است: closed (درخواست‌ها رد می‌شوند و می‌رسند)، open (درخواست‌ها فوراً رد می‌شوند) و half-open (چند درخواست آزمایشی تصمیم می‌گیرند دوباره بسته شود یا نه). منابع caller را حفظ می‌کند و به وابستگی فرصت بهبود می‌دهد.
