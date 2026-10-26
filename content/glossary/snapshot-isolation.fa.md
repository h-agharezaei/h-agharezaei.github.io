+++
title = "Snapshot isolation"
fa_title = "ایزولاسیون snapshot"
summary = "هر تراکنش از یک snapshot سازگار از داده می‌خواند که لحظه‌ی شروعش گرفته شده است."
category = "Databases"
related = ["isolation-level", "write-skew"]
posts = ["db-isolation-levels-anomalies"]
+++

در PostgreSQL، REPEATABLE READ همین‌طور کار می‌کند. خواندن هیچ‌وقت بلاک نمی‌شود و commitهای بعدی را نمی‌بیند، اما write skew همچنان ممکن است.
