+++
title = "Advisory lock"
summary = "قفلی که برنامه روی یک عدد تعریف می‌کند؛ دیتابیس آن را اعمال می‌کند اما معنایی برایش ندارد."
category = "Databases"
fa_title = "advisory lock"
related = ["lock"]
posts = ["db-locks-deadlocks"]
+++

`pg_advisory_lock(42)` و `pg_try_advisory_lock(42)` یک کلید دلخواه را قفل می‌کنند، نه ردیف یا جدول. همه باید از یک کلید استفاده کنند. برای «فقط یک نمونه این کار را اجرا کند» مناسب است.
