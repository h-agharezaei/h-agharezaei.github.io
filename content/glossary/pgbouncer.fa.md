+++
title = "PgBouncer"
fa_title = "PgBouncer"
summary = "یک connection pooler جدا که بین برنامه‌ها و PostgreSQL قرار می‌گیرد."
category = "Databases"
related = ["connection-pool","idle-in-transaction"]
posts = ["db-connection-pooling"]
+++

تعداد زیادی connection کلاینت چند connection سرور را share می‌کنند. در حالت session هر کلاینت در کل جلسه یک connection سرور دارد؛ در حالت transaction فقط در طول یک transaction آن را قرض می‌گیرد، پس وضعیت session بین transactionها منتقل نمی‌شود.
