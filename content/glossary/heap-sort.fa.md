+++
title = "Heap sort"
fa_title = "heap sort"
summary = "ساخت max-heap در جا، و بعد جابه‌جایی مکرر ریشه به انتها و sift down؛ O(n log n)، بدون حافظه‌ی اضافه و ناپایدار."
category = "Algorithms"
related = ["binary-heap", "heapify", "quicksort", "merge-sort"]
posts = ["algo-sorting"]
+++

Heap sort با [heapify](/fa/glossary/heapify/) slice را به max-heap تبدیل می‌کند، بعد بزرگ‌ترین عنصر (ریشه) را به انتهای heap در حال کوچک‌شدن می‌برد و heap را ترمیم می‌کند. کران O(n log n) تضمین‌شده دارد و بافر نمی‌خواهد، اما در حافظه می‌پرد و معمولاً مقایسه‌ی بیشتری از quicksort یا merge sort دارد.
