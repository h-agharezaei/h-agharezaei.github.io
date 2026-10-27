+++
title = "Characterization test"
summary = "تستی که رفتار فعلی کد را با همه‌ی باگ‌هایش ثبت می‌کند تا بتوان با اطمینان آن را تغییر داد."
category = "Engineering"
fa_title = "تست مشخصه‌نگار"
related = ["refactoring", "regression"]
posts = ["eng-refactoring-safely"]
+++

تست characterization (یا golden-master و snapshot) کد را روی ورودی‌های زیاد اجرا می‌کند، خروجی‌ها را در فایل ذخیره می‌کند و اگر بعداً خروجی‌ای فرق کند شکست می‌خورد. ادعا نمی‌کند رفتار درست است، فقط می‌گوید عوض نشده است.
