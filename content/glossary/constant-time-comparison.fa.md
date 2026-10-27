+++
title = "Constant-time comparison"
summary = "مقایسه‌ی رازها به‌شکلی که زمان اجرا به محل اولین تفاوت وابسته نباشد."
category = "Security"
fa_title = "مقایسه‌ی زمان‌ثابت"
related = ["password-hashing"]
posts = ["sec-password-hashing"]
+++

`==` معمولی ممکن است در اولین بایت متفاوت متوقف شود و از راه زمان اطلاعات نشت کند. در Go از `subtle.ConstantTimeCompare` استفاده کنید.
