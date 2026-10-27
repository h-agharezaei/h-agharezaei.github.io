+++
title = "Deadlock"
summary = "دو یا چند session هرکدام منتظر قفلی هستند که دیگری نگه داشته، پس هیچ‌کدام ادامه نمی‌دهد؛ دیتابیس یکی را قطع می‌کند."
category = "Databases"
fa_title = "deadlock"
related = ["lock", "transaction"]
posts = ["db-locks-deadlocks"]
+++

session A ردیف ۱ را دارد و ردیف ۲ را می‌خواهد، session B ردیف ۲ را دارد و ردیف ۱ را می‌خواهد. PostgreSQL بعد از `deadlock_timeout` این چرخه را می‌بیند و یک تراکنش را با SQLSTATE `40P01` لغو می‌کند. راه‌حل معمول گرفتن [قفل](/fa/glossary/lock/)ها در همه‌جا با یک ترتیب ثابت است.
