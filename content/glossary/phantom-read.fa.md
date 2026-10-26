+++
title = "Phantom read"
fa_title = "خواندن شبح"
summary = "اجرای یک کوئری دو بار در یک تراکنش و گرفتن مجموعه‌ی متفاوتی از ردیف‌ها."
category = "Databases"
related = ["isolation-level", "non-repeatable-read"]
posts = ["db-isolation-levels-anomalies"]
+++

ردیفی که با WHERE شما جور است را کس دیگری در این فاصله اضافه (یا حذف) و commit کرده است. ردیف‌هایی که قبلاً خواندید عوض نشده‌اند؛ ردیف تازه پیدا شده است.
