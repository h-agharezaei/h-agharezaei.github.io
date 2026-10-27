+++
title = "GIN index"
summary = "ایندکس وارونه در PostgreSQL که هر عنصر داخل یک مقدار (کلید JSON، کلمه) را به ردیف‌هایی که آن را دارند نگاشت می‌کند."
category = "Databases"
fa_title = "ایندکس GIN"
related = ["database-index", "b-tree", "jsonb", "tsvector"]
posts = ["db-jsonb-fulltext-search"]
+++

GIN (Generalized Inverted Index) برای مقدارهایی مناسب است که چند جزء دارند: سند JSONB، آرایه و بردار جست‌وجوی متنی. جست‌وجو برای هر جزء ردیف‌ها را پیدا و ترکیب می‌کند؛ نوشتن گران‌تر از [B-tree](/fa/glossary/b-tree/) است.
