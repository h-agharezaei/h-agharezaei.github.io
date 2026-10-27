+++
title = "Thundering herd"
summary = "وقتی یک رویداد چندین پروسه یا thread منتظر را بیدار می‌کند ولی فقط یکی می‌تواند از آن استفاده کند و کار هدر می‌رود."
category = "Linux"
fa_title = "thundering herd"
related = ["epoll", "socket"]
posts = ["linux-io-epoll", "ds-service-discovery-load-balancing", "linux-scripting-cron-safely"]
+++

نمونه‌ی کلاسیک چند worker است که روی یک listening socket منتظرند. man page مربوط به epoll(7) پرچم `EPOLLEXCLUSIVE` را برای محدود کردن این بیدارشدن‌ها نام می‌برد؛ معنای دقیقش را در man page ببینید.
