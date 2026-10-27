+++
title = "HttpOnly"
summary = "ویژگی کوکی که آن را از JavaScriptِ داخل صفحه پنهان می‌کند."
category = "Security"
fa_title = "HttpOnly"
related = ["xss"]
posts = ["sec-injection-xss", "sec-sessions-vs-jwt"]
+++

مرورگر کوکی را همچنان با درخواست‌ها می‌فرستد، ولی `document.cookie` نمی‌تواند آن را بخواند؛ پس یک باگ XSS به‌سادگی کوکی نشست را نمی‌دزدد.
