+++
title = "Failure detector"
summary = "مؤلفه‌ای که حدس می‌زند یک گره‌ی دور از کار افتاده یا نه، معمولاً از نرسیدن heartbeat در مهلت مشخص."
category = "Distributed"
fa_title = "تشخیص‌دهنده‌ی خرابی"
related = ["heartbeat", "gray-failure", "partial-failure"]
posts = ["ds-why-distributed-is-hard"]
+++

در شبکه‌ی ناهمگام دقیق نمی‌شود. timeout کوتاه خرابی واقعی را زود می‌فهمد ولی گره‌های سالم را هم مشکوک می‌کند؛ timeout بلند برعکس.
