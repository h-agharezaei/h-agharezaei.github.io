+++
title = "KMP algorithm"
fa_title = "الگوریتم KMP"
summary = "جست‌وجوی رشته با یک تابع شکست از پیش محاسبه‌شده، به‌طوری که اشاره‌گر متن هرگز عقب نمی‌رود."
category = "Algorithms"
related = ["rolling-hash", "rabin-karp"]
posts = ["algo-string-algorithms"]
+++

KMP (Knuth–Morris–Pratt) متن را با O(n + m) مقایسه جست‌وجو می‌کند. پس از ناهم‌خوانی، از ساختار پیشوندیِ خودِ الگو تصمیم می‌گیرد چه مقدار از تطابق را نگه دارد.
