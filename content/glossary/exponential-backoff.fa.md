+++
title = "Exponential backoff"
summary = "افزایش فاصله‌ی بین تلاش‌ها پس از هر شکست، با دو برابر شدن تا سقف مشخص."
category = "Distributed"
fa_title = "بک‌آف نمایی"
related = ["jitter", "retry-storm"]
posts = ["ds-timeouts-retries-backoff", "ds-case-studies"]
+++

بعد از تلاش n‌ام، کلاینت تقریباً `min(cap, base * 2^n)` صبر می‌کند. این به سرور تحت فشار فرصت بهبود می‌دهد، ولی کلاینت‌هایی که با هم شکست خورده‌اند با هم هم تلاش می‌کنند، مگر [jitter](/fa/glossary/jitter/) اضافه شود.
