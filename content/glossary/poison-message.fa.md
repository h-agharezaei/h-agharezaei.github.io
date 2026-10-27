+++
title = "Poison message"
summary = "پیامی که هر بار consumer را به شکست می‌کشد، پس redelivery هرگز موفق نمی‌شود."
category = "Distributed"
fa_title = "poison message"
related = ["dlq", "at-least-once-delivery"]
posts = ["ds-messaging-event-driven"]
+++

بدون محدودیت تعداد تحویل برای همیشه گیر می‌کند یا حلقه می‌زند؛ راه‌حل معمول max-deliver و مقصد dead-letter است.
