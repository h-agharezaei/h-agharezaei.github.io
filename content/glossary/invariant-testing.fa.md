+++
title = "Invariant testing"
fa_title = "تست invariant"
summary = "صدا زدن دنباله‌های تصادفی از تابع‌ها و چک کردن بعد از هر فراخوانی که یک خاصیت کل سیستم هنوز برقرار است."
category = "Blockchain"
related = ["fuzzing", "invariant", "shrinking", "property-based-testing"]
posts = ["bc-foundry-testing-fuzzing", "bc-erc20-erc721"]
+++

شکل state‌دار [fuzzing](/fa/glossary/fuzzing/). مثال: کل عرضه‌ی توکن برابر جمع همه‌ی موجودی‌هاست. معمولاً یک قرارداد handler ورودی تصادفی را به فراخوانی معتبر تبدیل می‌کند و دنباله‌ی شکست‌خورده به یک مثال نقض کوتاه کوچک می‌شود.
