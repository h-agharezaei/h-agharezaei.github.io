+++
title = "Trigram"
summary = "گروه سه‌حرفی پشت‌سرهم؛ مقایسه‌ی مجموعه‌ی trigramهای دو رشته یک امتیاز شباهت می‌دهد که برای تطبیق تقریبی به کار می‌رود."
category = "Databases"
fa_title = "Trigram"
related = ["gin-index"]
posts = ["db-jsonb-fulltext-search"]
+++

extension به نام `pg_trgm` تابع `similarity()`، عملگر `%` و operator classهای trigram برای [ایندکس GIN](/fa/glossary/gin-index/) را می‌دهد که `LIKE '%text%'` را هم سریع می‌کنند.
