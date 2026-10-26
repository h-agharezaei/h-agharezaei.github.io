+++
title = "Normalization"
summary = "هر واقعیت فقط یک‌بار ذخیره شود؛ جدول‌ها را برای این هدف می‌شکنیم."
category = "Databases"
fa_title = "نرمال‌سازی"
related = ["primary-key", "foreign-key", "denormalization"]
posts = ["db-schema-design-normalization"]
+++

نرمال‌سازی یعنی شکستن یک جدول به جدول‌های کوچک‌تر تا هر واقعیت (مثلاً ایمیل یک مشتری یا قیمت یک محصول) فقط در یک جا ذخیره شود. این کار anomalyهای update، insert و delete را از بین می‌برد. مراحل معمول آن 1NF، 2NF و 3NF نام دارند. برای سمت مقابل ماجرا [denormalization](/fa/glossary/denormalization/) را ببینید.
