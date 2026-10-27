+++
title = "DNS"
summary = "سیستمی که نام‌ها را به رکوردهایی مثل آدرس IP نگاشت می‌کند."
category = "Networking"
fa_title = "دی‌اِن‌اِس"
related = ["recursive-resolver", "authoritative-server", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute", "ds-service-discovery-load-balancing"]
+++

DNS یک پایگاه داده‌ی توزیع‌شده و سلسله‌مراتبی است: root به دامنه‌های سطح بالا و آن‌ها به name serverهای هر دامنه واگذار می‌کنند. کلاینت‌ها رکوردها (A، AAAA، MX، TXT و ...) را با نام از آن می‌پرسند.
