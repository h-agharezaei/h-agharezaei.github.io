+++
title = "Transaction"
summary = "گروهی از دستورها که دیتابیس آن‌ها را یک واحد می‌بیند: یا همه اثر می‌کنند یا هیچ‌کدام."
category = "Databases"
fa_title = "تراکنش"
related = ["acid", "savepoint"]
posts = ["db-transactions-acid", "db-mvcc-vacuum"]
+++

در PostgreSQL هر دستور داخل یک تراکنش اجرا می‌شود؛ بدون `BEGIN` هر دستور تراکنش خودش را دارد (autocommit). `COMMIT` تغییرها را ماندگار می‌کند و `ROLLBACK` آن‌ها را دور می‌ریزد.
