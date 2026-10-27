+++
title = "Property-based testing"
fa_title = "تست خاصیت‌محور"
summary = "قاعده‌ای را که باید برای همه‌ی ورودی‌ها برقرار باشد با ورودی‌های خودکار می‌آزماید."
category = "Engineering"
related = ["tdd", "test-pyramid", "shrinking", "fuzzing"]
posts = ["eng-property-based-testing"]
+++

به‌جای مثال‌های ثابت، یک خاصیت می‌نویسید (مثلاً دوبار معکوس کردن همان اصل را می‌دهد) و ابزار ورودی‌های تصادفی زیادی می‌سازد تا مثال نقض پیدا کند. Go ابزار `testing/quick` و کتابخانه‌ی `rapid` را دارد.
