+++
title = "synchronous_commit"
summary = "تنظیم PostgreSQL که تعیین می‌کند COMMIT صبر کند تا WAL آن روی دیسک flush شود یا نه."
category = "Databases"
fa_title = "synchronous_commit"
related = ["wal", "acid"]
posts = ["db-transactions-acid", "db-replication-streaming"]
+++

با مقدار پیش‌فرض `on`، commit فقط بعد از flush شدن WAL برمی‌گردد و همین آن را durable می‌کند. مقدار `off` سریع‌تر است ولی crash می‌تواند چند commit آخر را از بین ببرد (دیتابیس سالم می‌ماند).
