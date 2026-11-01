+++
title = "Checks-effects-interactions"
summary = "ترتیب تابع: اول بررسی ورودی، بعد نوشتن state، و فقط در آخر صدا زدن قراردادهای دیگر یا فرستادن ETH."
category = "Blockchain"
fa_title = "الگوی checks-effects-interactions"
related = ["reentrancy", "smart-contract"]
posts = ["bc-contract-security"]
+++

اگر state پیش از خروج کنترل از قرارداد نهایی شده باشد، callback چیزی برای سوءاستفاده پیدا نمی‌کند. دفاع اصلی در برابر [reentrancy](/fa/glossary/reentrancy/) است و قفل `nonReentrant` لایه‌ی دوم.
