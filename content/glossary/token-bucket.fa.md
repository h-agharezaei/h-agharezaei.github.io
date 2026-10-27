+++
title = "Token bucket"
summary = "limiterی که توکن را با نرخ ثابت پر می‌کند و برای هر درخواست یکی خرج می‌کند؛ burst تا ظرفیت مجاز است."
category = "Distributed"
fa_title = "سطل توکن"
related = ["rate-limiting", "sliding-window"]
posts = ["ds-distributed-rate-limiting"]
+++

وضعیت دو عدد است: تعداد توکن و زمان آخرین پر شدن. leaky bucket وقتی به‌عنوان meter به کار رود همان تصمیم‌ها را می‌گیرد.
