+++
title = "RBAC"
fa_title = "کنترل دسترسی نقش‌محور"
summary = "کنترل دسترسی نقش‌محور: کاربر نقش می‌گیرد و هر نقش به مجموعه‌ای از مجوزها نگاشت می‌شود."
category = "Security"
related = ["authorization", "deny-by-default"]
posts = ["sec-authorization-rbac-idor"]
+++

در RBAC هر کاربر یک نقش (viewer، editor، admin) دارد و هر نقش به مجموعه‌ای از مجوزها مثل `doc:delete` نگاشت می‌شود. کد مجوز را بررسی می‌کند، نه نام نقش را، پس نقش‌ها بدون دست زدن به handlerها عوض می‌شوند.
