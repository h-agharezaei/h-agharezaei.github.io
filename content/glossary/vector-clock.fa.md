+++
title = "Vector clock"
summary = "یک شمارنده برای هر process؛ مقایسه‌ی دو vector دقیقاً می‌گوید قبل، بعد یا هم‌زمان."
category = "Distributed"
fa_title = "vector clock (ساعت برداری)"
related = ["happens-before", "lamport-clock", "version-vector"]
posts = ["ds-logical-clocks"]
+++

هر process خانه‌ی خودش را زیاد می‌کند و هنگام receive max عنصر به عنصر می‌گیرد. هزینه‌اش vectorی به اندازه‌ی تعداد شرکت‌کننده‌هاست.
