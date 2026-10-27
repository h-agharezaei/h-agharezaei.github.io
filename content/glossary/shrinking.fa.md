+++
title = "Shrinking"
fa_title = "کوچک‌سازی مثال نقض (shrinking)"
summary = "کوچک کردن ورودی تصادفی شکست‌خورده تا کوچک‌ترین ورودی که هنوز شکست می‌خورد."
category = "Engineering"
related = ["property-based-testing", "fuzzing"]
posts = ["eng-property-based-testing"]
+++

وقتی خاصیتی روی یک ورودی تصادفی بزرگ شکست می‌خورد، کتابخانه نسخه‌های کوچک‌تر را امتحان می‌کند و کوچک‌ترینِ شکست‌خورده را نگه می‌دارد. به‌جای یک slice سی‌وهفت عضوی، `[0 1 0]` را اشکال‌زدایی می‌کنید.
