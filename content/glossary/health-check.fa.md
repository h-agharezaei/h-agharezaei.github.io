+++
title = "Health check"
summary = "بررسی‌ای که به load balancer می‌گوید backend می‌تواند ترافیک بگیرد یا نه."
category = "Networking"
fa_title = "health check"
related = ["load-balancer"]
posts = ["net-load-balancer-l4-l7"]
+++

بررسی فعال با یک تایمر probe می‌فرستد (مثلاً `GET /healthz`)؛ بررسی غیرفعال خطاهای ترافیک واقعی را می‌پاید. بعد از چند شکست، backend از چرخه خارج می‌شود.
