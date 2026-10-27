+++
title = "Unsafe deserialization"
summary = "ساخت دوباره‌ی شیء از بایت‌های نامطمئن با قالبی که هنگام decode می‌تواند کد اجرا کند، مثل pickle در Python."
category = "Security"
fa_title = "deserialization ناامن"
related = ["pickle", "ssrf"]
posts = ["sec-ssrf-deserialization"]
+++

بعضی قالب‌ها فقط داده را توصیف نمی‌کنند، بلکه می‌گویند برای ساختن دوباره کدام تابع صدا زده شود. اگر مهاجم بایت‌ها را کنترل کند، تابع را او انتخاب می‌کند. قالب‌های داده‌ی ساده مثل JSON همراه با schema validation این مشکل را ندارند. نگاه کنید به [pickle](/fa/glossary/pickle/).
