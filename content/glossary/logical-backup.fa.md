+++
title = "Logical backup"
summary = "بک‌آپی از SQL یا داده‌ی ردیف‌ها (pg_dump، COPY) به‌جای کپی فایل‌های داده."
category = "Databases"
fa_title = "بک‌آپ منطقی"
related = ["pitr", "wal"]
posts = ["db-backup-restore-pitr"]
+++

بین نسخه‌ها قابل حمل است و می‌تواند یک جدول را برگرداند، ولی فقط یک لحظه را ثبت می‌کند و موقع restore ایندکس‌ها را از نو می‌سازد. بک‌آپ فیزیکی فایل‌های داده را کپی می‌کند و با WAL برای PITR ترکیب می‌شود.
