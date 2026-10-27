+++
title = "Optimistic concurrency"
fa_title = "همزمانی خوش‌بینانه (optimistic concurrency)"
summary = "قفل نمی‌گیرید؛ با نسخه‌ای که خوانده‌اید می‌نویسید و اگر دیگری زودتر نوشته باشد شکست می‌خورید، سپس دوباره می‌خوانید و تلاش می‌کنید."
category = "Distributed"
related = ["event-sourcing", "idempotency"]
posts = ["ds-cqrs-event-sourcing"]
+++

در event store کلید اصلی روی (stream_id, version) این کار را می‌کند: نویسنده‌ی دوم نسخه‌ی ۳ خطای unique violation می‌گیرد.
