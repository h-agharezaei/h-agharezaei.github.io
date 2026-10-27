+++
title = "Table rewrite"
summary = "یک ALTER که کل جدول را در فایل جدید کپی می‌کند و در تمام این مدت قفل سنگین نگه می‌دارد."
category = "Databases"
fa_title = "بازنویسی جدول"
related = ["migration", "lock"]
posts = ["db-zero-downtime-migrations"]
+++

با `pg_relation_filenode()` قبل و بعد از دستور می‌شود فهمید: عدد جدید یعنی فایل جدید. روی جدول بزرگ، بازنویسی تا پایان کپی جلوی خواندن و نوشتن را می‌گیرد.
