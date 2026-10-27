+++
title = "Table partitioning"
summary = "یک جدول منطقی بزرگ را بر اساس یک کلید (بازه‌ی تاریخ، فهرست مقدار یا hash) به جدول‌های فیزیکی کوچک‌تر (پارتیشن) تقسیم می‌کند."
category = "Databases"
fa_title = "پارتیشن‌بندی جدول"
related = ["partition-pruning","default-partition","primary-key"]
posts = ["db-partitioning"]
+++

یک جدول منطقی بزرگ را بر اساس یک کلید (بازه‌ی تاریخ، فهرست مقدار یا hash) به جدول‌های فیزیکی کوچک‌تر (پارتیشن) تقسیم می‌کند. در PostgreSQL خودِ جدول والد ردیفی ندارد و هر ردیف دقیقاً در یک پارتیشن است. کوئری و insert همچنان با اسم والد انجام می‌شود. [partition pruning](/fa/glossary/partition-pruning/) را ببینید.
