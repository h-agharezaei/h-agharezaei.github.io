+++
title = "Idle in transaction"
fa_title = "idle in transaction"
summary = "جلسه‌ای که transaction باز کرده و کاری نمی‌کند، ولی هنوز connection و قفل‌هایش را نگه داشته."
category = "Databases"
related = ["transaction","connection-pool","statement-timeout"]
posts = ["db-connection-pooling"]
+++

در `pg_stat_activity` به شکل `state = 'idle in transaction'` دیده می‌شود: BEGIN فرستاده شده و برنامه دیگر statement نمی‌فرستد. این connection قابل استفاده‌ی دوباره نیست و قفل‌ها و snapshot نگه داشته می‌شوند. `idle_in_transaction_session_timeout` چنین جلسه‌هایی را می‌بندد. ← [transaction](/fa/glossary/transaction/).
