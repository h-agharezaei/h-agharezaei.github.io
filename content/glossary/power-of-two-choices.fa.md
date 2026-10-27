+++
title = "Power of two choices"
summary = "قاعده‌ی load balancing: دو instance تصادفی انتخاب کن و درخواست را به آنی بده که صف کوتاه‌تری دارد."
category = "Distributed"
fa_title = "دو انتخاب تصادفی"
related = ["load-balancer", "service-discovery"]
posts = ["ds-service-discovery-load-balancing"]
+++

برای هر درخواست فقط دو عدد بار لازم دارد، ولی در شبیه‌سازی (در مقاله) به انتخاب همیشگی کم‌بارترین instance نزدیک می‌ماند و از random خیلی بهتر است.
