+++
title = "Dijkstra's algorithm"
fa_title = "الگوریتم Dijkstra"
summary = "کوتاه‌ترین مسیر از یک مبدأ در گراف با وزن نامنفی، با گسترش همیشگی نزدیک‌ترین رأس تمام‌نشده."
category = "Algorithms"
related = ["relaxation", "priority-queue", "bellman-ford"]
posts = ["algo-shortest-paths-dijkstra"]
+++

کوتاه‌ترین مسیر از یک مبدأ در گراف با وزن نامنفی، با گسترش همیشگی نزدیک‌ترین رأس تمام‌نشده.

یک فاصله‌ی موقت برای هر رأس و یک priority queue نگه می‌دارد. رأسی که pop شد فاصله‌اش نهایی است؛ برای همین وزن منفی آن را خراب می‌کند.
