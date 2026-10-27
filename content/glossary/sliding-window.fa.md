+++
title = "Sliding window counter"
summary = "limiter تقریبی که پنجره‌ی ثابت قبلی را به نسبت هم‌پوشانی‌اش با بازه‌ی اخیر وزن می‌دهد."
category = "Distributed"
fa_title = "شمارنده‌ی پنجره‌ی لغزان"
related = ["rate-limiting", "token-bucket"]
posts = ["ds-distributed-rate-limiting", "ds-case-studies"]
+++

برآورد برابر است با previous_count * (1 - elapsed/window) + current_count. برخلاف sliding log که هر timestamp را نگه می‌دارد، فقط چند عدد برای هر کلید لازم دارد.
