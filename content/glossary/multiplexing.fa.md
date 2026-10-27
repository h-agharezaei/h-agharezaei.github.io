+++
title = "Multiplexing"
summary = "فرستادن هم‌زمان چند درخواست و پاسخ مستقل روی یک اتصال."
category = "Networking"
fa_title = "چندگانه‌سازی (multiplexing)"
related = ["alpn", "head-of-line-blocking"]
posts = ["net-http2", "net-grpc-over-http2"]
+++

در HTTP/2 هر درخواست یک stream شماره‌دار است و frameهای stream‌های مختلف روی یک اتصال TCP در هم می‌آیند. برای هر درخواست در حال انجام لازم نیست اتصال جدا باز شود.
