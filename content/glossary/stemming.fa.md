+++
title = "Stemming"
summary = "برگرداندن کلمه به ریشه‌اش تا شکل‌های مختلف یک کلمه با هم تطبیق شوند؛ مثلاً running و runs و run همه می‌شوند run."
category = "Databases"
fa_title = "Stemming"
related = ["tsvector"]
posts = ["db-jsonb-fulltext-search"]
+++

PostgreSQL این کار را با یک dictionary انجام می‌دهد که جزو text search configuration است، مثل `english`. configuration به نام `simple` اصلاً stemming نمی‌کند. stemming به زبان وابسته است و شکل‌های بی‌قاعده مثل `ran` ممکن است کوتاه نشوند.
