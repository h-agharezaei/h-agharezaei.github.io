+++
title = "Keyset pagination"
summary = "صفحه‌بندی با «ردیف‌های بعد از این کلید» به‌جای «N ردیف را رد کن»."
category = "Engineering"
fa_title = "صفحه‌بندی مبتنی بر کلید"
related = ["pagination"]
posts = ["eng-api-design-versioning-pagination"]
+++

کلاینت کلید مرتب‌سازی آخرین ردیفی را که دیده می‌فرستد (معمولاً داخل یک cursor مبهم) و سرور ردیف‌های بعد از آن را برمی‌گرداند. درج و حذف قبل از آن نقطه صفحه‌ی بعد را جابه‌جا نمی‌کند، و با index روی کلید مرتب‌سازی ردیف‌های ردشده اسکن نمی‌شوند. [pagination](/fa/glossary/pagination/) را ببینید.
