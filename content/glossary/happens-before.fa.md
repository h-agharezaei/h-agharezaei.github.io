+++
title = "Happens-before"
summary = "رابطه‌ی علّیت به صورت ترتیب جزئی: ترتیب برنامه، send قبل از receive و تعدی؛ رویدادهای بدون چنین مسیری هم‌زمان‌اند."
category = "Distributed"
fa_title = "happens-before (رخ‌داد پیش از)"
related = ["lamport-clock", "vector-clock", "causal-consistency"]
posts = ["ds-logical-clocks"]
+++

اگر a پیش از b رخ دهد، a می‌توانسته روی b اثر بگذارد. اگر هیچ‌کدام پیش از دیگری نباشد، رویدادها هم‌زمان‌اند و هیچ ساعتی نمی‌تواند ترتیب درستی بین آن‌ها بگذارد.
