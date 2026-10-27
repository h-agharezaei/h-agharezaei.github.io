+++
title = "Sharding"
summary = "داده‌ی یک سیستم را با یک کلید (shard key) بین چند node تقسیم می‌کند تا هر node فقط بخشی از آن را نگه دارد."
category = "Distributed"
fa_title = "شاردینگ (sharding)"
related = ["consistent-hashing", "partitioning", "hot-key"]
posts = ["ds-sharding-consistent-hashing"]
+++

هر ردیف (یا کلید) دقیقاً به یک shard می‌رسد که با بازه، hash یا یک جدول جستجو (directory) انتخاب می‌شود. ظرفیت نوشتن و جای داده را زیاد می‌کند، ولی کوئری و تراکنشی که چند shard را لمس کند گران می‌شود. با [partitioning](/fa/glossary/partitioning/) درون یک node فرق دارد.
