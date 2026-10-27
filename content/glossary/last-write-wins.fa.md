+++
title = "Last write wins"
summary = "قاعده‌ای برای حل تعارض که مقدار با بزرگ‌ترین timestamp را نگه می‌دارد و بقیه را دور می‌ریزد."
category = "Distributed"
fa_title = "آخرین نوشتن برنده است"
related = ["clock-skew"]
posts = ["ds-why-distributed-is-hard", "ds-cap-pacelc", "ds-logical-clocks"]
+++

ساده است، ولی با ساعت‌های ناهمگام ممکن است نوشتنی که واقعاً تازه‌تر است timestamp کوچک‌تری داشته باشد و بی‌صدا از بین برود.
