+++
title = "Migration"
summary = "یک تغییر نسخه‌دار در schema دیتابیس که با اسکریپت یا ابزار و به ترتیب اجرا می‌شود."
category = "Databases"
fa_title = "مایگریشن (migration)"
related = ["table-rewrite", "expand-contract"]
posts = ["db-zero-downtime-migrations"]
+++

نمونه‌اش اضافه کردن ستون یا ایندکس است. خطر خود SQL نیست، [قفل](/fa/glossary/lock/)هایی است که روی جدولِ در حال استفاده می‌گیرد. ابزارهایی مثل goose یا Flyway فقط فایل‌ها را به ترتیب اجرا می‌کنند و یک دستور خطرناک را امن نمی‌کنند.
