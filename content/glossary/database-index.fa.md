+++
title = "Database index"
summary = "ساختار مرتب و جداگانه‌ای که دیتابیس را بدون خواندن کل جدول به ردیف‌ها می‌رساند."
category = "Databases"
fa_title = "اندیس دیتابیس"
related = ["b-tree", "query-plan"]
posts = ["db-indexes-btree-explain", "py-data-csv-sqlite"]
+++

ایندکس مقدارهای یک یا چند ستون را همراه اشاره‌گر به ردیف‌های جدول نگه می‌دارد. خواندنی که با آن جور باشد سریع‌تر می‌شود، ولی هر insert، update و delete باید ایندکس را هم به‌روز کند. رایج‌ترین نوع آن [B-tree](/fa/glossary/b-tree/) است.
