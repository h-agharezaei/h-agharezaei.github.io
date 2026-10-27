+++
title = "statement_timeout"
fa_title = "statement_timeout"
summary = "تنظیمی در PostgreSQL که هر statement طولانی‌تر از زمان داده‌شده را لغو می‌کند."
category = "Databases"
related = ["lock-timeout","idle-in-transaction"]
posts = ["db-connection-pooling"]
+++

وقتی statement از حد بگذرد سرور آن را با SQLSTATE `57014` لغو می‌کند و connection قابل استفاده می‌ماند. می‌شود آن را برای هر session، role یا database تنظیم کرد. ← [lock timeout](/fa/glossary/lock-timeout/).
