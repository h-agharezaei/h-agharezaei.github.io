+++
title = "Type affinity"
fa_title = "type affinity (تمایل نوع)"
summary = "قاعده‌ی SQLite که ستون یک نوع را ترجیح می‌دهد و در صورت امکان مقدار را تبدیل می‌کند، ولی سخت‌گیرانه اجبارش نمی‌کند."
category = "Databases"
related = []
posts = ["py-data-csv-sqlite"]
+++

در SQLite ستونی که `INTEGER` تعریف شده affinity عددی دارد: متن `'12'` به عدد صحیح 12 تبدیل می‌شود، ولی `'abc'` بدون خطا به‌صورت متن ذخیره می‌شود. هر مقدار نوع خودش را دارد. جدول‌های `STRICT` نوع تعریف‌شده را اجبار می‌کنند.
