+++
title = "Isolation level"
fa_title = "سطح ایزولاسیون"
summary = "تنظیمی که تعیین می‌کند یک تراکنش چقدر از کارِ تراکنش‌های هم‌زمان را ببیند."
category = "Databases"
related = ["transaction", "acid", "snapshot-isolation"]
posts = ["db-isolation-levels-anomalies"]
+++

استاندارد SQL چهار سطح READ UNCOMMITTED، READ COMMITTED، REPEATABLE READ و SERIALIZABLE را نام می‌برد. سطح قوی‌تر ناهنجاری‌های بیشتری را ممنوع می‌کند، اما تراکنش‌های بیشتری ممکن است abort شوند. پیش‌فرض PostgreSQL برابر READ COMMITTED است.
