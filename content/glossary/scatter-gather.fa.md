+++
title = "Scatter-gather"
summary = "فرستادن کوئری به همه‌ی shardها و ادغام پاسخ‌های جزئی، وقتی کوئری شامل shard key نیست."
category = "Distributed"
fa_title = "scatter-gather"
related = ["sharding", "hot-key"]
posts = ["ds-sharding-consistent-hashing"]
+++

هزینه با تعداد shardها بالا می‌رود: هر کوئری به ازای هر shard یک درخواست می‌سازد و کندترین shard تأخیر را تعیین می‌کند. کوئری‌ای که shard key دارد فقط به یک shard می‌رود.
