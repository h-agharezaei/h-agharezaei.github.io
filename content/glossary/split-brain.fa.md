+++
title = "Split-brain"
summary = "دو node هر دو خود را primary می‌دانند و نوشتن‌های متفاوت می‌پذیرند."
category = "Databases"
fa_title = "split-brain"
related = ["failover","replication"]
posts = ["db-replication-streaming", "ds-consensus-raft"]
+++

بعد از promote، primary قدیمی اگر هنوز روشن باشد نوشتن می‌پذیرد و تاریخچه‌ها از هم جدا می‌شوند. ادغام بعدی دستی است و اغلب با از دست رفتن داده همراه.
