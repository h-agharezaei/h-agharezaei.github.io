+++
title = "Generated column"
summary = "ستونی که مقدارش با یک عبارت از ستون‌های دیگر همان ردیف محاسبه و خودکار ذخیره می‌شود."
category = "Databases"
fa_title = "ستون generated"
related = ["tsvector", "database-index"]
posts = ["db-jsonb-fulltext-search"]
+++

در PostgreSQL، `GENERATED ALWAYS AS (expr) STORED` مقدار را در هر insert و update دوباره حساب می‌کند و نمی‌شود مستقیم رویش نوشت. کاربرد رایج: یک `tsvector` از پیش محاسبه‌شده که می‌شود ایندکسش کرد.
