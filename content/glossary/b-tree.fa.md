+++
title = "B-tree"
summary = "درخت متوازنی از page‌های هم‌اندازه با کلیدهای مرتب، نوع پیش‌فرض ایندکس در PostgreSQL."
category = "Databases"
fa_title = "B-tree"
related = ["database-index", "binary-search"]
posts = ["db-indexes-btree-explain"]
+++

جست‌وجو از page ریشه شروع می‌شود، در هر سطح یک اشاره‌گر را دنبال می‌کند و به page برگی می‌رسد که کلید در آن است. چون درخت پهن و کم‌عمق است، حتی میلیون‌ها ردیف فقط چند page خواندن لازم دارند؛ نزولی شبیه [جست‌وجوی دودویی](/fa/glossary/binary-search/) با زمان O(log n).
