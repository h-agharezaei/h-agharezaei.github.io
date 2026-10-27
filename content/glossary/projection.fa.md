+++
title = "Projection"
fa_title = "projection (read model)"
summary = "یک read model که با مصرف رویدادها ساخته می‌شود و جدولی مناسب query نگه می‌دارد؛ با replay می‌توان آن را حذف و دوباره ساخت."
category = "Distributed"
related = ["cqrs", "event-sourcing", "idempotency"]
posts = ["ds-cqrs-event-sourcing"]
+++

checkpoint آخرین موقعیت رویداد پردازش‌شده را نگه می‌دارد تا بعد از restart از همان‌جا ادامه دهد.
