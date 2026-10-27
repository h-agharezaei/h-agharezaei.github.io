+++
title = "Byte order mark"
fa_title = "BOM (نشانه‌ی ترتیب بایت)"
summary = "چند بایت نامرئی در ابتدای فایل متنی؛ در UTF-8 همان EF BB BF است و فایل را UTF-8 معرفی می‌کند."
category = "Python"
related = []
posts = ["py-data-csv-sqlite"]
+++

BOM چند بایت در ابتدای فایل است. UTF-8 به آن نیاز ندارد، ولی Excel برای تشخیص encoding آن را می‌نویسد یا انتظار دارد. اگر چنین فایلی را با `utf-8` ساده بخوانید، BOM به شکل کاراکتر `\ufeff` به اول نام ستون اول می‌چسبد؛ `utf-8-sig` آن را حذف می‌کند.
