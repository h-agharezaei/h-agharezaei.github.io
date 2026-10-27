+++
title = "SameSite"
summary = "ویژگی کوکی که تعیین می‌کند مرورگر در درخواست‌های بین‌سایتی کوکی را کِی بفرستد."
category = "Security"
fa_title = "SameSite"
related = ["csrf", "httponly"]
posts = ["sec-sessions-vs-jwt", "sec-csrf-cors-headers"]
+++

`Lax` کوکی را در POST و زیردرخواست‌های بین‌سایتی نمی‌فرستد ولی در ناوبری معمولی می‌فرستد؛ `Strict` سخت‌گیرانه‌تر است؛ `None` به `Secure` نیاز دارد.
