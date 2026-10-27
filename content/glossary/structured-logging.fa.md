+++
title = "Structured logging"
summary = "نوشتن هر خط لاگ به‌صورت یک شیء JSON با فیلدهای نام‌دار، به‌جای متن آزاد."
category = "Node.js"
fa_title = "لاگ ساختاریافته"
related = ["request-id"]
posts = ["node-fastify-api", "eng-postmortems-blameless", "linux-logs-journalctl", "sec-logging-audit-incident-response"]
+++

فیلدهایی مثل `level`، `reqId` و `res.statusCode` را ابزارها بدون regex فیلتر می‌کنند. Pino، لاگر داخل Fastify، هر خط را یک شیء JSON می‌نویسد.
