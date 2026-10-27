+++
title = "Quicksort"
fa_title = "quicksort"
summary = "Quicksort در جا، با انتخاب pivot و افراز slice به دو طرف آن، و مرتب‌کردن بازگشتی هر طرف؛ به‌طور میانگین O(n log n)."
category = "Algorithms"
related = ["merge-sort", "heap-sort", "stable-sort", "big-o"]
posts = ["algo-sorting"]
+++

Quicksort یک **pivot** انتخاب می‌کند، کوچک‌ترها را سمت چپ و بزرگ‌ترها را سمت راست آن می‌برد و هر طرف را جداگانه مرتب می‌کند. آرایه‌ی اضافه نمی‌خواهد، ولی pivot بد (مثلاً همیشه عنصر اول روی ورودی مرتب) آن را به O(n^2) می‌رساند. pivot میانه‌ی سه‌تایی و cutoff به insertion sort برای بازه‌های کوچک راه‌حل‌های رایج‌اند. پایدار (stable) نیست.
