+++
title = "Bloom filter"
fa_title = "Bloom filter"
summary = "ساختاری با آرایه‌ی بیت که یا می‌گوید «حتماً نیست» یا «شاید هست»؛ منفی‌ی اشتباه ندارد."
category = "Algorithms"
related = ["hash-table","consistent-hashing"]
posts = ["algo-bloom-filter-consistent-hashing"]
+++

Bloom filter برای هر کلید درج‌شده k بیت را روشن می‌کند و در جست‌وجو همان k بیت را می‌خواند. اگر یکی صفر باشد کلید حتماً اضافه نشده؛ اگر همه یک باشند ممکن است مثبت اشتباه باشد. حافظه‌ی خیلی کمتری از set می‌خواهد ولی حذف ندارد (نوع counting دارد). نگاه کنید به [جدول هش](/fa/glossary/hash-table/).
