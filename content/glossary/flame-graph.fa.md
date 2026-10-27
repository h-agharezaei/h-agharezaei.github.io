+++
title = "Flame graph"
fa_title = "فلیم‌گراف"
summary = "تصویری از stackهای نمونه‌برداری‌شده که عرض هر جعبه نشان می‌دهد تابع چند بار روی stack بوده."
category = "Linux"
related = ["perf", "cpu-profile"]
posts = ["linux-strace-perf"]
+++

**فلیم‌گراف** stackهای نمونه‌برداری‌شده را روی هم می‌چیند: محور افقی زمان نیست و جعبه‌ی پهن یعنی آن تابع (با فراخوانی‌هایش) در نمونه‌های زیادی بوده. اسکریپت‌های FlameGraph از Brendan Gregg آن را از خروجی `perf` می‌کشند.
