+++
title = "Sargable"
fa_title = "sargable (قابل‌ایندکس)"
summary = "شرطی که طوری نوشته شده که ایندکس بتواند برایش به کار برود."
category = "Databases"
related = ["selectivity"]
posts = ["db-planner-statistics", "db-composite-partial-covering-indexes", "db-slow-query-case-study"]
+++

`email = 'a'` sargable است؛ `lower(email) = 'a'` نیست مگر ایندکسی روی `lower(email)` باشد. cast روی ستون یا `%` ابتدایی هم آن را خراب می‌کند.
