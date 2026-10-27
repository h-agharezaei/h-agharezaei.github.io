+++
title = "Backfill"
summary = "پر کردن ستون جدید برای ردیف‌های موجود، در دسته‌های کوچک تا قفل‌ها و تراکنش‌ها کوتاه بمانند."
category = "Databases"
fa_title = "backfill"
related = ["expand-contract", "migration"]
posts = ["db-zero-downtime-migrations", "ds-deployment-strategies"]
+++

یک `UPDATE` غول‌آسا همه‌ی قفل‌های ردیف را یک‌جا نگه می‌دارد و یک‌باره ردیف مرده می‌سازد. حلقه‌ای که در هر دسته یک بازه‌ی id را به‌روز می‌کند تراکنش‌ها را کوچک نگه می‌دارد.
