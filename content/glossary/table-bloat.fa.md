+++
title = "Table bloat"
summary = "فضای هدررفته در جدول یا ایندکس به‌خاطر نسخه‌های مرده‌ای که دوباره استفاده نشده‌اند."
category = "Databases"
fa_title = "table bloat"
related = ["dead-tuple", "vacuum"]
posts = ["db-mvcc-vacuum"]
+++

`VACUUM` ساده فضا را داخل همان فایل قابل استفاده‌ی دوباره می‌کند ولی معمولاً فایل را کوچک نمی‌کند؛ `VACUUM FULL` جدول را بازنویسی می‌کند و کوچک می‌کند.
