+++
title = "Memory leak"
summary = "حافظه‌ای که دیگر لازم نیست اما هنوز قابل دسترسی است و garbage collector نمی‌تواند آزادش کند."
category = "Node.js"
fa_title = "نشت حافظه"
related = ["garbage-collector", "heap-snapshot"]
posts = ["node-profiling-memory-shutdown"]
+++

نمونه‌ی کلاسیک یک `Map` یا آرایه در سطح module است که با هر درخواست بزرگ‌تر می‌شود و هیچ‌وقت کوچک نمی‌شود.
