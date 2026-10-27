+++
title = "Level-triggered and edge-triggered"
summary = "دو روش گزارش آمادگی: تا وقتی داده منتظر است (level) یا فقط هنگام رسیدن داده‌ی تازه (edge)."
category = "Linux"
fa_title = "level-triggered و edge-triggered"
related = ["epoll", "kqueue", "non-blocking-io"]
posts = ["linux-io-epoll"]
+++

level-triggered تا وقتی داده‌ی نخوانده مانده در هر انتظار descriptor را آماده گزارش می‌کند. edge-triggered فقط یک بار به ازای هر تغییر گزارش می‌دهد، پس باید تا EAGAIN بخوانید وگرنه گیر می‌کنید. در kqueue رفتار شبه‌edge از `EV_CLEAR` می‌آید.
