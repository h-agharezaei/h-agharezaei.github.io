+++
title = "Hash chain"
summary = "هر رکورد hash رکورد قبلی را نگه می‌دارد، پس ویرایش، حذف یا جابه‌جایی همه‌ی پیوندهای بعدی را می‌شکند."
category = "Security"
fa_title = "hash chain (زنجیره‌ی hash)"
related = ["audit-log", "hmac"]
posts = ["sec-logging-audit-incident-response"]
+++

hash chain لاگ را «دست‌کاری‌نمایان» می‌کند، نه «دست‌کاری‌ناپذیر»: کسی که کل فایل را بازنویسی کند زنجیره را دوباره حساب می‌کند. checkpointهای امضاشده در جای دیگر این شکاف را می‌بندند.
