+++
title = "Index Only Scan"
summary = "یک node در plan که کوئری را فقط از ایندکس جواب می‌دهد، بی‌آنکه سراغ جدول برود."
category = "Databases"
fa_title = "Index Only Scan"
related = ["covering-index", "visibility-map"]
posts = ["db-composite-partial-covering-indexes", "db-mvcc-vacuum"]
+++

هنوز [visibility map](/fa/glossary/visibility-map/) را چک می‌کند؛ برای صفحه‌هایی که all-visible نیستند ردیف جدول را می‌خواند (در خروجی `Heap Fetches`).
