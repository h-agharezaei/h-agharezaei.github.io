+++
title = "WAL"
summary = "write-ahead log: PostgreSQL هر تغییر را پیش از دست زدن به فایل‌های داده در یک لاگ ترتیبی ثبت می‌کند."
category = "Databases"
fa_title = "WAL"
related = ["database-index"]
posts = ["db-indexes-btree-explain", "db-transactions-acid", "db-replication-streaming"]
+++

این لاگ ریکاوری بعد از crash و replication را ممکن می‌کند. هر تغییر در جدول یا ایندکس رکورد WAL تولید می‌کند، پس تعداد بایت‌های WAL راهی قطعی برای سنجش کار یک نوشتن است.
