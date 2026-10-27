+++
title = "HMAC"
summary = "کد احراز پیام ساخته‌شده از هش و کلید مخفی؛ برخلاف sha256(secret||msg) در برابر length extension مقاوم است."
category = "Security"
fa_title = "HMAC"
related = ["length-extension-attack", "constant-time-comparison"]
posts = ["sec-crypto-mistakes", "sec-logging-audit-incident-response"]
+++

در Go: `hmac.New(sha256.New, key)`، نوشتن پیام و `Sum(nil)`. برچسب‌ها را با `hmac.Equal` مقایسه کنید.
