+++
title = "Union-find"
fa_title = "مجموعه‌های جدا از هم"
summary = "ساختاری که نگه می‌دارد کدام عنصرها در یک گروه‌اند، با Find (کدام گروه؟) و Union (ادغام دو گروه)."
category = "Algorithms"
related = ["path-compression", "union-by-size", "amortized-analysis"]
posts = ["algo-tries-union-find", "algo-greedy-backtracking"]
+++

union-find یا disjoint set عنصرها را در گروه‌های بدون اشتراک نگه می‌دارد. `Find(x)` نماینده‌ی گروه x را برمی‌گرداند و `Union(a, b)` دو گروه را ادغام می‌کند. با path compression و union by size، کل دنباله‌ی عملیات طبق منابع تقریباً خطی است.
