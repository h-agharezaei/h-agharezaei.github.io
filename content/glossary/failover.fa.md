+++
title = "Failover"
summary = "جابه‌جایی به یک standby به‌عنوان primary جدید وقتی قدیمی از کار می‌افتد."
category = "Databases"
fa_title = "failover"
related = ["replication","split-brain"]
posts = ["db-replication-streaming"]
+++

خود PostgreSQL فقط دستور promote را می‌دهد؛ تشخیص خرابی، انتخاب standby و از مدار خارج‌کردن primary قدیمی کار ابزارهای بیرونی مثل Patroni یا repmgr است.
