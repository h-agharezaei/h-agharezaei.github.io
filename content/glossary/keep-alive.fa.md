+++
title = "Keep-alive"
summary = "استفاده‌ی مجدد از یک اتصال TCP برای چند درخواست HTTP، به‌جای باز کردن اتصال تازه برای هرکدام."
category = "Node.js"
fa_title = "Keep-alive"
related = ["graceful-shutdown"]
posts = ["node-http-server", "net-http1-by-hand", "node-profiling-memory-shutdown", "net-load-balancer-l4-l7"]
+++

در keep-alive بعد از پاسخ، اتصال باز می‌ماند تا درخواست بعدی از همان استفاده کند. سرور بعد از مدتی بی‌کاری آن را می‌بندد (در Node.js با `keepAliveTimeout`).
