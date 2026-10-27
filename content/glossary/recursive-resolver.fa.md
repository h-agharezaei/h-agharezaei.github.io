+++
title = "Recursive resolver"
summary = "سرور DNS که کل جست‌وجو را برای کلاینت انجام می‌دهد و نتیجه را cache می‌کند."
category = "Networking"
fa_title = "recursive resolver"
related = ["authoritative-server", "dns", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute"]
+++

برنامه‌ی شما از یک recursive resolver می‌پرسد (مثلاً یک resolver عمومی یا مال ISP). او از root به TLD و سپس به authoritative server می‌رود، جواب نهایی را برمی‌گرداند و در مسیر cache می‌کند.
