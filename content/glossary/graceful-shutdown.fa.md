+++
title = "Graceful shutdown"
summary = "متوقف کردن سرور بدون پذیرش کار تازه، به‌طوری که درخواست‌های در حال اجرا تمام شوند."
category = "Node.js"
fa_title = "خاموشی تمیز"
related = ["keep-alive"]
posts = ["node-http-server", "node-fastify-api", "node-nats-jetstream", "node-profiling-memory-shutdown"]
+++

با رسیدن سیگنال توقف مثل SIGTERM، فرایند اتصال تازه نمی‌پذیرد، اتصال‌های بی‌کار را می‌بندد، منتظر درخواست‌های در حال اجرا می‌ماند و بعد با کد ۰ خارج می‌شود. معمولاً یک timer هم اگر چیزی تمام نشد خروج را اجباری می‌کند.
