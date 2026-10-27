+++
title = "SQLSTATE"
summary = "کد خطای استاندارد پنج‌کاراکتری، مثلاً 23505 برای نقض unique."
category = "Databases"
fa_title = "SQLSTATE"
related = ["foreign-key", "primary-key"]
posts = ["db-relational-sql-essentials", "db-isolation-levels-anomalies", "node-postgres-pg"]
+++

برنامه باید روی SQLSTATE تصمیم بگیرد، نه متن خطا. کلاس 23 نقض یکپارچگی است: 23505 unique، 23503 foreign key و 23514 check.
