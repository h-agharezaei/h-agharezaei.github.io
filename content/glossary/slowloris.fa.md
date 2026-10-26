+++
title = "Slowloris"
summary = "حمله‌ی منع سرویسی که در آن کلاینت درخواست را بسیار کند می‌فرستد تا اتصال‌های سرور را اشغال نگه دارد."
category = "Node.js"
fa_title = "Slowloris"
related = ["keep-alive"]
posts = ["node-http-server"]
+++

کلاینت کند هدر یا بدنه را چند بایت چند بایت می‌فرستد و هرگز تمامش نمی‌کند، پس هر اتصال منابع سرور را اشغال می‌کند. timeoutهایی مثل `headersTimeout` و `requestTimeout` دفاع اصلی‌اند.
