+++
title = "SharedArrayBuffer"
summary = "بلوک حافظه‌ای که هم‌زمان برای چند thread دیده می‌شود و با Atomics به کار می‌رود."
category = "Node.js"
fa_title = "بافر مشترک"
related = ["worker-threads", "race-condition"]
posts = ["node-worker-threads-cluster"]
+++

`SharedArrayBuffer` بین worker threadها کپی نمی‌شود: همه بایت‌های یکسان را می‌بینند. خواندن و نوشتن ساده روی آن race دارد، پس برای به‌روزرسانی تقسیم‌ناپذیر از `Atomics` (مثلاً `Atomics.add`) استفاده کنید.
