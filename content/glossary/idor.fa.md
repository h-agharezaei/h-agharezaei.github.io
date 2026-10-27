+++
title = "IDOR"
summary = "IDOR (ارجاع مستقیم ناامن به شیء): endpoint شیء را با شناسه‌اش برمی‌گرداند بی‌آنکه بررسی کند فراخواننده اجازه‌ی دیدنش را دارد."
category = "Security"
fa_title = "IDOR"
related = ["owasp-top-10"]
posts = ["sec-owasp-top10-in-code"]
+++

مثال: `GET /orders/2` سفارش باب را به آلیس می‌دهد. راه‌حل بررسی مالکیت در سرور برای هر خواندن است.
