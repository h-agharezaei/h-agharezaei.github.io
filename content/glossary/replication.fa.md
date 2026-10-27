+++
title = "Replication"
summary = "نگه‌داشتن یک نسخه‌ی دوم که دائم به‌روز می‌شود از دیتابیس روی سرور دیگر."
category = "Databases"
fa_title = "replication"
related = ["wal","lsn","failover"]
posts = ["db-replication-streaming", "ds-replication-quorum"]
+++

در streaming replication پستگرس، primary جریان WAL را به standbyها می‌فرستد و آن‌ها replay می‌کنند. standbyها فقط خواندن را جواب می‌دهند و قابل promote هستند. بک‌آپ نیست: نوشتن اشتباه هم replicate می‌شود.
