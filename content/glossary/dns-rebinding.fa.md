+++
title = "DNS rebinding"
summary = "نامی که برای بررسی به آدرسی بی‌خطر و برای اتصال به آدرسی داخلی resolve می‌شود."
category = "Security"
fa_title = "DNS rebinding"
related = ["ssrf", "toctou", "dns"]
posts = ["sec-ssrf-deserialization"]
+++

اگر کد جواب یک lookup را بررسی کند و بعد با نام وصل شود، lookup دوم می‌تواند آدرس دیگری بدهد. دفاع این است که یک بار resolve کنید و به همان IP بررسی‌شده وصل شوید. نگاه کنید به [TOCTOU](/fa/glossary/toctou/).
