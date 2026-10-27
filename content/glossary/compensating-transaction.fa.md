+++
title = "Compensating transaction"
summary = "کاری جدید که اثر یک قدم قبلاً commit‌شده را از نظر معنایی خنثی می‌کند، مثل refund برای یک charge."
category = "Distributed"
fa_title = "تراکنش جبرانی"
related = ["saga", "idempotency"]
posts = ["ds-saga-vs-2pc", "ds-modular-monolith-vs-microservices", "ds-capstone"]
+++

این کار rollback نیست: قدم اصلی واقعاً انجام شده و در تاریخچه می‌ماند. جبران باید idempotent و قابل تکرار باشد، چون ممکن است دو بار برسد یا شکست بخورد و دوباره اجرا شود.
