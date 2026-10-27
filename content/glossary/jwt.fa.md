+++
title = "JWT"
summary = "توکن امضاشده (header.payload.signature) که claimها را حمل می‌کند؛ امضا شده، رمزنگاری نشده."
category = "Security"
fa_title = "JWT"
related = ["session", "csrf"]
posts = ["sec-sessions-vs-jwt", "sec-oauth2-oidc"]
+++

هر کسی payload را می‌خواند؛ فقط امضا جلوی تغییر را می‌گیرد. تا `exp` معتبر می‌ماند مگر سرور وضعیت اضافه نگه دارد.
