+++
title = "Composite index"
summary = "یک ایندکس روی چند ستون که اول بر اساس ستون اول، بعد دوم و ... مرتب است."
category = "Databases"
fa_title = "ایندکس ترکیبی"
related = ["covering-index", "partial-index"]
posts = ["db-composite-partial-covering-indexes"]
+++

ترتیب مهم است: `(a, b)` فیلتر روی `a` یا روی `a` و `b` را خوب جواب می‌دهد، ولی فیلتر فقط روی `b` را نه. ستون‌های equality را اول و ستون range را آخر بگذارید.
