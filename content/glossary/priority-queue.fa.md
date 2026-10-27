+++
title = "Priority queue"
fa_title = "صف اولویت"
summary = "ظرفی انتزاعی که همیشه آیتم با بالاترین اولویت را بیرون می‌دهد، نه قدیمی‌ترین را."
category = "Algorithms"
related = ["binary-heap", "big-o"]
posts = ["algo-heaps-priority-queues", "algo-greedy-backtracking"]
+++

صف اولویت دو عمل `Push` و `Pop` دارد و `Pop` فوری‌ترین آیتم (کوچک‌ترین یا بزرگ‌ترین کلید) را برمی‌گرداند. این یک interface است، نه یک ساختار حافظه؛ پیاده‌سازی معمول آن [binary heap](/fa/glossary/binary-heap/) است. اولویت‌های برابر ترتیب مشخصی ندارند، مگر اینکه tie-break مثل شماره‌ی ترتیب اضافه کنید.
