+++
title = "Query plan"
summary = "درخت قدم‌هایی که دیتابیس برای اجرای یک query انتخاب می‌کند و EXPLAIN نشان می‌دهد."
category = "Databases"
fa_title = "query plan"
related = ["database-index"]
posts = ["db-indexes-btree-explain"]
+++

planner برای هر راه ممکن اجرای query (اسکن جدول، استفاده از ایندکس، ترتیب join) یک هزینه تخمین می‌زند و ارزان‌ترین را برمی‌گزیند. `EXPLAIN` پلن را نشان می‌دهد و `EXPLAIN ANALYZE` query را اجرا هم می‌کند و تعداد ردیف‌های واقعی را اضافه می‌کند.
