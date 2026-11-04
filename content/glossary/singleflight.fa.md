+++
title = "singleflight"
summary = "یک کمک‌کتابخانه‌ی Go (golang.org/x/sync/singleflight) که فراخوانی‌های هم‌زمان با یک کلید را یک اجرا و یک نتیجه‌ی مشترک می‌کند."
category = "Go"
fa_title = "ادغام فراخوانی‌های هم‌کلید"
related = ["rate-limiting", "ttl"]
posts = ["go-rate-limiting-caching"]
+++

`Group.Do(key, fn)` تابع `fn` را برای هر کلید یک بار اجرا می‌کند؛ فراخوانی‌هایی که وسط اجرا برسند منتظر می‌مانند و همان نتیجه و همان خطا را می‌گیرند. راه معمول جلوگیری از [cache stampede](/fa/glossary/cache-stampede/) است.
