+++
title = "Heap snapshot"
summary = "ثبت همه‌ی objectهای زنده‌ی heap همراه با اندازه و ارجاع‌ها، برای پیدا کردن اینکه چه چیزی حافظه را نگه داشته."
category = "Node.js"
fa_title = "اسنپ‌شات heap"
related = ["memory-leak", "garbage-collector"]
posts = ["node-profiling-memory-shutdown"]
+++

در Node.js با `v8.writeHeapSnapshot()` نوشته می‌شود. فایل JSON است و می‌تواند به بزرگی خود heap باشد، پس بعد از استفاده پاکش کنید.
