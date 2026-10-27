+++
title = "SKIP LOCKED"
summary = "گزینه‌ای برای `SELECT ... FOR UPDATE` که به‌جای انتظار، ردیف‌های قفل‌شده‌ی دیگران را رد می‌کند؛ برای ساخت صف کار."
category = "Databases"
fa_title = "SKIP LOCKED"
related = ["lock"]
posts = ["db-locks-deadlocks"]
+++

با `FOR UPDATE SKIP LOCKED` هر worker ردیف‌هایی را برمی‌دارد که کسی قفل نکرده، پس چند worker هم‌زمان کارهای متفاوتی از یک جدول می‌گیرند. برای جدول‌های شبیه صف است و برای خواندن عمومی مناسب نیست، چون نتیجه به قفل‌های همان لحظه بستگی دارد.
