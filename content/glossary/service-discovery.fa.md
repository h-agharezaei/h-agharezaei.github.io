+++
title = "Service discovery"
summary = "پیدا کردن نشانی‌های فعلی instanceهای یک سرویس در حالی که می‌آیند و می‌روند."
category = "Distributed"
fa_title = "کشف سرویس"
related = ["service-registry", "load-balancer", "dns"]
posts = ["ds-service-discovery-load-balancing"]
+++

instanceها شروع می‌شوند، crash می‌کنند و جابه‌جا می‌شوند، پس نشانی‌ها را نمی‌شود ثابت نوشت. client از DNS یا [registry](/fa/glossary/service-registry/) یا یک message bus می‌پرسد الان چه کسی زنده است.
