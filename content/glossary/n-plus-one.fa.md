+++
title = "N+1 queries"
fa_title = "N+1 query"
summary = "یک query برای گرفتن لیست و بعد یک query جدا برای هر آیتم لیست."
category = "Databases"
related = ["correlated-subquery", "sql-join"]
posts = ["db-slow-query-case-study", "py-sqlalchemy-postgres"]
+++

برنامه ۱۰۰ سفارش را با یک query می‌گیرد و بعد ۱۰۰ query دیگر برای گرفتن مشتری هر سفارش اجرا می‌کند. هر query تنهایی سریع است و هیچ پلنی بد به نظر نمی‌رسد؛ هزینه در رفت‌وبرگشت‌هاست. راه‌حل یک query با join یا `WHERE id = ANY(...)` است.
