+++
title = "Hash slot"
summary = "یکی از تعداد ثابتی سطل منطقی که کلیدها در آن hash می‌شوند؛ کل slot به node داده یا بین node‌ها جابه‌جا می‌شود، نه تک‌تک کلیدها."
category = "Distributed"
fa_title = "hash slot"
related = ["sharding", "consistent-hashing"]
posts = ["ds-sharding-consistent-hashing"]
+++

کلید با slot = hash(key) mod S به یک slot می‌رسد (S ثابت است) و یک جدول slotها را به node‌ها نگاشت می‌کند. افزودن node چند slot را جابه‌جا می‌کند و نگاشت کلید به slot هرگز عوض نمی‌شود. طبق مستندات، Redis Cluster از ۱۶۳۸۴ slot استفاده می‌کند.
