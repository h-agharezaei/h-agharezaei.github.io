+++
title = "libuv"
summary = "کتابخانه‌ی C زیر Node.js که event loop، I/O ناهمگام و thread pool را فراهم می‌کند."
category = "Node.js"
fa_title = "libuv"
related = ["event-loop", "thread-pool"]
posts = ["node-event-loop", "linux-io-epoll"]
+++

Node.js با libuv بدون بلاک کردن thread جاوااسکریپت با سیستم‌عامل کار می‌کند. libuv بعضی کارها (فایل، crypto، DNS lookup) را هم در thread pool خودش اجرا می‌کند.
