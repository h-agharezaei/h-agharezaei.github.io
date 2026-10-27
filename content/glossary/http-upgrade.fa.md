+++
title = "HTTP Upgrade"
summary = "درخواستی که از سرور می‌خواهد اتصال را به پروتکل دیگری ببرد (پاسخ 101 Switching Protocols)."
category = "Networking"
fa_title = "HTTP Upgrade"
related = ["http", "websocket"]
posts = ["net-websocket"]
+++

کلاینت `Upgrade: websocket` و `Connection: Upgrade` می‌فرستد. اگر سرور موافق باشد `101 Switching Protocols` برمی‌گرداند و از آن لحظه بایت‌های آن اتصال دیگر HTTP نیستند.
