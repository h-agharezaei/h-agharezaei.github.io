+++
title = "Mutation testing"
summary = "سنجش مجموعه‌ی تست با این که وقتی کد عمداً خراب شود شکست بخورد یا نه."
category = "Engineering"
fa_title = "تست جهش"
related = ["characterization-test", "tdd"]
posts = ["eng-refactoring-safely"]
+++

ابزار تغییرهای کوچک زیادی (mutant) می‌سازد، مثلاً >= را به > تبدیل می‌کند، و تست‌ها را روی هرکدام اجرا می‌کند. mutantای که هیچ تستی نگیرد حفره‌ای را نشان می‌دهد که coverage خطی نشان نمی‌دهد.
