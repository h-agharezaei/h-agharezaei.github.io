+++
title = "SQL injection"
summary = "حمله‌ای که در آن ورودی کاربر بخشی از متن SQL می‌شود و معنای آن را عوض می‌کند."
category = "Security"
fa_title = "SQL injection (تزریق SQL)"
related = ["sqlstate"]
posts = ["node-postgres-pg"]
+++

وقتی SQL را با چسباندن رشته‌ها می‌سازید رخ می‌دهد. راه دفاع، query پارامتری (`$1`) است: مقدارها جدا از متن SQL ارسال می‌شوند و هرگز به‌عنوان SQL خوانده نمی‌شوند.
