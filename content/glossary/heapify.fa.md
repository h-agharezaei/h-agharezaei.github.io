+++
title = "Heapify"
fa_title = "heapify"
summary = "تبدیل یک slice نامرتب به heap در جا و در O(n)، با پایین‌بردن گره‌ها از آخرین والد تا ریشه."
category = "Algorithms"
related = ["binary-heap", "big-o"]
posts = ["algo-heaps-priority-queues"]
+++

Heapify از اندیس `n/2-1` شروع می‌کند و هر گره را پایین می‌برد. بیشتر گره‌ها نزدیک برگ‌ها هستند و کم جابه‌جا می‌شوند، پس مجموع کار O(n) است؛ در بدترین حالت ارزان‌تر از n بار push (که O(n log n) است). نگاه کنید به [Binary heap](/fa/glossary/binary-heap/).
