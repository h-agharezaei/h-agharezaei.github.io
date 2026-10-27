+++
title = "Branch by abstraction"
summary = "جایگزینی تدریجی کد با پنهان کردن قدیم و جدید پشت یک interface."
category = "Engineering"
fa_title = "branch با انتزاع"
related = ["feature-flag","trunk-based-development","characterization-test"]
posts = ["eng-feature-flags-trunk-based", "eng-legacy-code"]
+++

در branch by abstraction جلوی پیاده‌سازی قدیمی یک interface می‌گذارید، پیاده‌سازی تازه را کنارش اضافه می‌کنید و بینشان سوییچ می‌کنید (اغلب با feature flag). بازنویسی در گام‌های کوچک به شاخه‌ی اصلی می‌رسد، نه روی شاخه‌ای بلندمدت.
