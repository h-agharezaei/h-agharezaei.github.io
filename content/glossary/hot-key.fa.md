+++
title = "Hot key"
summary = "کلیدی که آن‌قدر ترافیک می‌گیرد که shard صاحبش حتی با پخش یکنواخت بقیه‌ی کلیدها زیر بار می‌ماند."
category = "Distributed"
fa_title = "کلید داغ (hot key)"
related = ["sharding", "scatter-gather"]
posts = ["ds-sharding-consistent-hashing", "ds-distributed-rate-limiting", "ds-case-studies"]
+++

عوض کردن hash کمکی نمی‌کند چون همان کلید همیشه به همان shard می‌رود. راه رایج، شکستن کلید با یک پسوند (salt) است که نوشتن را پخش می‌کند ولی خواندن باید همه‌ی پسوندها را بخواند.
