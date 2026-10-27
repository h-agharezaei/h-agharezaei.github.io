+++
title = "tsvector"
summary = "نوع داده‌ای در PostgreSQL که یک سند را به شکل فهرست مرتب‌شده‌ی کلمه‌های نرمال‌شده (lexeme) با موقعیتشان نگه می‌دارد؛ برای جست‌وجوی متنی."
category = "Databases"
fa_title = "tsvector"
related = ["stemming", "gin-index"]
posts = ["db-jsonb-fulltext-search"]
+++

`to_tsvector('english', 'running shoes')` نتیجه‌ی `'run':1 'shoe':2` می‌دهد. آن را با عملگر `@@` با یک `tsquery` تطبیق می‌دهید و با [ایندکس GIN](/fa/glossary/gin-index/) ایندکس می‌کنید.
