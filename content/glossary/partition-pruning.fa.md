+++
title = "Partition pruning"
summary = "planner پارتیشن‌هایی را که به‌خاطر فیلتر روی کلید پارتیشن نمی‌توانند ردیف مطابق داشته باشند کنار می‌گذارد."
category = "Databases"
fa_title = "حذف پارتیشن‌ها (partition pruning)"
related = ["partitioning","query-planner"]
posts = ["db-partitioning", "ds-sharding-consistent-hashing"]
+++

planner پارتیشن‌هایی را که به‌خاطر فیلتر روی کلید پارتیشن نمی‌توانند ردیف مطابق داشته باشند کنار می‌گذارد. بدون شرط روی کلید پارتیشن باید همه‌ی پارتیشن‌ها اسکن شوند. این کار با تنظیم `enable_partition_pruning` کنترل می‌شود. [پارتیشن‌بندی](/fa/glossary/partitioning/) را ببینید.
