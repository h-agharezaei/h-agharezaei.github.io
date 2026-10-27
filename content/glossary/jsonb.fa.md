+++
title = "JSONB"
summary = "نوع ستونی در PostgreSQL که JSON را به شکل باینری پارس‌شده نگه می‌دارد و می‌شود رویش ایندکس ساخت و کوئری زد."
category = "Databases"
fa_title = "JSONB"
related = ["gin-index", "database-index"]
posts = ["db-jsonb-fulltext-search"]
+++

برخلاف `json` ساده، `jsonb` ترتیب کلیدها و کلید تکراری را نگه نمی‌دارد، ولی عملگرهایی مثل `@>` (شامل بودن) و `?` (وجود کلید) و ایندکس GIN را پشتیبانی می‌کند. تا قید (constraint) نگذارید، JSONB نه schema دارد نه بررسی نوع. [ایندکس GIN](/fa/glossary/gin-index/) را ببینید.
