+++
title = "Surrogate key"
summary = "شناسه‌ی مصنوعی ردیف بدون معنای کسب‌وکاری، مثل یک شماره‌ی identity."
category = "Databases"
fa_title = "کلید جایگزین"
related = ["primary-key"]
posts = ["db-schema-design-normalization"]
+++

surrogate key شناسه‌ای است که خود دیتابیس می‌سازد، مثلاً عدد `GENERATED ALWAYS AS IDENTITY`. برخلاف natural key مثل ایمیل، هرگز تغییر نمی‌کند. با این حال روی natural key هم یک قید UNIQUE بگذارید. [primary key](/fa/glossary/primary-key/) را ببینید.
