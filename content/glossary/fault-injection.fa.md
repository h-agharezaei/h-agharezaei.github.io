+++
title = "Fault injection"
summary = "ایجاد عمدی تأخیر، خطا یا crash در یک وابستگی برای دیدن واکنش سیستم."
category = "Distributed"
fa_title = "تزریق خطا"
related = ["chaos-engineering", "blast-radius", "idempotency"]
posts = ["ds-fault-injection-testing", "ds-capstone"]
+++

خطاها را می‌شود با proxy بین کلاینت و سرور، با wrapper دور HTTP client در unit test یا با kill کردن process تزریق کرد. هدف پیدا کردن timeout گم‌شده، retry ناایمن و فرض‌های غلط است، پیش از آنکه production پیدایشان کند.
