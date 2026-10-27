+++
title = "Connection pool"
summary = "مجموعه‌ای از اتصال‌های باز به دیتابیس که قرض داده و دوباره استفاده می‌شوند."
category = "Databases"
fa_title = "connection pool (استخر اتصال)"
related = ["transaction"]
posts = ["node-postgres-pg", "db-connection-pooling"]
+++

باز کردن اتصال به دیتابیس کند است و سرور تعداد اتصال‌ها را محدود می‌کند. pool چند اتصال باز نگه می‌دارد، برای هر query یا تراکنش یکی را قرض می‌دهد و بعد از release پس می‌گیرد. وقتی همه مشغول باشند، درخواست‌ها منتظر می‌مانند.
