+++
title = "Covering index"
summary = "ایندکسی که همه‌ی ستون‌های موردنیاز کوئری را دارد و نیازی به خواندن جدول نیست."
category = "Databases"
fa_title = "ایندکس پوششی"
related = ["index-only-scan", "composite-index"]
posts = ["db-composite-partial-covering-indexes"]
+++

در PostgreSQL ستون‌های اضافه را با `INCLUDE` می‌آورید؛ در ایندکس ذخیره می‌شوند ولی در مرتب‌سازی نقشی ندارند. این کار [Index Only Scan](/fa/glossary/index-only-scan/) را ممکن می‌کند.
