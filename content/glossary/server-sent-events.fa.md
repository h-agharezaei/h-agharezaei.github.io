+++
title = "Server-Sent Events"
summary = "جریان یک‌طرفه و متنی از رویدادها از سرور به مرورگر روی یک پاسخ معمولی HTTP."
category = "Networking"
fa_title = "SSE"
related = ["http", "websocket"]
posts = ["net-websocket"]
+++

سرور پاسخی با `Content-Type: text/event-stream` را باز نگه می‌دارد و خط‌های `data:` می‌نویسد؛ `EventSource` مرورگر خودش دوباره وصل می‌شود. کلاینت روی این کانال پیامی نمی‌فرستد.
