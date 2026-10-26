+++
title = "Savepoint"
summary = "نقطه‌ای نام‌دار داخل یک تراکنش که می‌شود بدون رها کردن کل تراکنش به آن برگشت."
category = "Databases"
fa_title = "savepoint"
related = ["transaction"]
posts = ["db-transactions-acid"]
+++

`SAVEPOINT s1` نقطه را علامت می‌زند و `ROLLBACK TO s1` هرچه بعد از آن بوده را برمی‌گرداند؛ تراکنش باز و قابل استفاده می‌ماند.
