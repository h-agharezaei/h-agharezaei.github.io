+++
title = "At-least-once delivery"
summary = "broker هر پیام را یک بار یا بیشتر تحویل می‌دهد و هرگز صفر بار، پس تکرار ممکن است."
category = "Distributed"
fa_title = "تحویل at-least-once"
related = ["idempotency", "jetstream", "dlq"]
posts = ["ds-messaging-event-driven", "ds-cqrs-event-sourcing", "ds-case-studies"]
+++

وقتی پیام ack نشده دوباره تحویل می‌شود همین رفتار را می‌گیرید. پس consumerها باید idempotent باشند.
