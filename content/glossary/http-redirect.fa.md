+++
title = "HTTP redirect"
summary = "ریدایرکت پاسخ 3xx با هدر Location است که به کلاینت می‌گوید URL دیگری را بخواهد."
category = "Networking"
fa_title = "ریدایرکت HTTP"
related = ["http"]
posts = ["net-troubleshooting-curl-traceroute"]
+++

ریدایرکت پاسخی مثل 301 یا 302 با هدر `Location` است. کلاینت باید درخواست تازه‌ای به آن URL بفرستد؛ curl این کار را فقط با `-L` می‌کند. نگاه کنید به [HTTP](/fa/glossary/http/).
