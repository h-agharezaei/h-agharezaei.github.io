+++
title = "Page cache"
fa_title = "کش صفحه (page cache)"
summary = "کش حافظه‌ی کرنل برای محتوای فایل‌ها که خواندن دوباره‌ی یک فایل را از دیسک بی‌نیاز می‌کند و در صورت نیاز به حافظه پس گرفته می‌شود."
category = 'Linux'
related = ["rss", "overcommit"]
posts = ["linux-memory-page-cache-oom"]
+++

طبق proc_meminfo(5) فیلد `Cached` کش حافظه‌ای فایل‌های خوانده‌شده از دیسک است (همان page cache). چون قابل پس‌گرفتن است در `MemAvailable` حساب می‌شود؛ پس buff/cache بزرگ عادی است و نشت حافظه نیست.
