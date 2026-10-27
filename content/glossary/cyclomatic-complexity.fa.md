+++
title = "Cyclomatic complexity"
summary = "شمارش مسیرهای تصمیم مستقل در یک تابع."
category = "Engineering"
fa_title = "پیچیدگی سیکلوماتیک"
related = ["refactoring"]
posts = ["eng-refactoring-safely", "eng-technical-debt"]
+++

ابزارهایی مثل gocyclo یک را با هر if، for، case غیر default و عملگرهای && و || جمع می‌زنند. عدد بالا یعنی مسیرهای زیاد برای تست و فهمیدن. نشانه‌ای برای پیدا کردن جای مشکل است، نه نمره‌ی کیفیت.
