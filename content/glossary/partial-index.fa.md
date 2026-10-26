+++
title = "Partial index"
summary = "ایندکسی که فقط ردیف‌هایی را پوشش می‌دهد که شرط WHERE را دارند."
category = "Databases"
fa_title = "ایندکس جزئی"
related = ["primary-key"]
posts = ["db-schema-design-normalization", "db-composite-partial-covering-indexes"]
+++

ایندکس جزئی با یک WHERE ساخته می‌شود و فقط ردیف‌های منطبق را دارد. همراه با UNIQUE قاعده‌هایی مثل «هر مشتری حداکثر یک سفارش باز» را اعمال می‌کند، در حالی که ردیف‌های با وضعیت‌های دیگر هر تعداد می‌توانند باشند.
