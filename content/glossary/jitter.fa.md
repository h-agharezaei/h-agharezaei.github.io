+++
title = "Jitter"
summary = "تصادف اضافه‌شده به فاصله‌ی retry تا کلاینت‌ها هم‌زمان تلاش نکنند."
category = "Distributed"
fa_title = "جیتر"
related = ["exponential-backoff", "retry-storm"]
posts = ["ds-timeouts-retries-backoff", "ds-fault-injection-testing", "ds-service-discovery-load-balancing"]
+++

در full jitter فاصله به‌صورت یکنواخت در `[0, backoff]` انتخاب می‌شود؛ در equal jitter نیمی از backoff ثابت و بقیه تصادفی است. هر دو retry‌های کلاینت‌های زیاد را در زمان پخش می‌کنند. [بک‌آف نمایی](/fa/glossary/exponential-backoff/) را ببینید.
