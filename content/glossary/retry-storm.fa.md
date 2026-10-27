+++
title = "Retry storm"
summary = "فشار اضافه‌ای که از retry هم‌زمان کلاینت‌ها روی سرور از پیش آسیب‌دیده ایجاد می‌شود."
category = "Distributed"
fa_title = "طوفان retry"
related = ["exponential-backoff", "jitter", "retry-budget"]
posts = ["ds-timeouts-retries-backoff", "ds-fault-injection-testing"]
+++

یک قطعی کوتاه باعث شکست درخواست‌های زیادی می‌شود؛ retry آن‌ها همراه ترافیک تازه می‌رسد و می‌تواند سرور را حتی بعد از رفع خطای اصلی تحت فشار نگه دارد. backoff با [jitter](/fa/glossary/jitter/) و [retry budget](/fa/glossary/retry-budget/) آن را محدود می‌کنند.
