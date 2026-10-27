+++
title = "Refactoring"
summary = "تغییر ساختار کد بدون تغییر رفتار قابل مشاهده‌ی آن."
category = "Engineering"
fa_title = "رفکتور"
related = ["characterization-test", "regression"]
posts = ["eng-refactoring-safely"]
+++

refactoring یعنی بازنویسی درون کد (نام‌ها، تابع‌ها، تو در تویی) در حالی که هر ورودی همان خروجی قبلی را بدهد. اگر رفتار عمداً عوض شود، آن تغییر دیگری است و باید در commit جدا برود. بدون تستی که رفتار را ثابت کند نمی‌دانید کدام‌یک را انجام داده‌اید.
