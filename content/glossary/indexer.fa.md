+++
title = "Indexer"
fa_title = "indexer"
summary = "سرویسی که بلاک‌ها یا logهای رویداد را از نود می‌خواند و در دیتابیسی ذخیره می‌کند که سریع پرس‌وجو شود."
category = "Blockchain"
related = ["event-log", "chain-reorganization", "confirmation"]
posts = ["bc-event-indexer-go"]
+++

نود به «در بلاک N چه شد» خوب جواب می‌دهد و به «همه‌ی انتقال‌های آدرس X» بد. indexer یک cursor نگه می‌دارد، اجرای دوباره نباید خرابش کند و بعد از [reorg](/fa/glossary/chain-reorganization/) باید ردیف‌ها را برگرداند.
