+++
title = "Clock skew"
summary = "اختلاف ساعت دو ماشین در یک لحظه‌ی واقعی."
category = "Distributed"
fa_title = "اختلاف ساعت"
related = ["last-write-wins", "monotonic-clock"]
posts = ["ds-why-distributed-is-hard", "ds-logical-clocks"]
+++

حتی با همگام‌سازی زمان، ساعت ماشین‌ها کمی و گاهی خیلی با هم فرق دارد. هر قاعده‌ای که رویدادها را با مقایسه‌ی timestamp ماشین‌های مختلف مرتب کند، این خطا را به ارث می‌برد.
