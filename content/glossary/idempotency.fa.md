+++
title = "Idempotency"
summary = "پردازش چندباره‌ی یک عملیات همان اثر پردازش یک‌باره را دارد."
category = "Messaging"
fa_title = "خودتوان‌بودن"
related = ["jetstream", "dlq", "outbox-pattern"]
posts = ["nats-jetstream-idempotency", "node-nats-jetstream"]
+++

سیستم‌های پیام با تحویل at-least-once ممکن است پیام را دوباره تحویل بدهند، پس handlerها باید تکرار را تحمل کنند. روش‌های رایج: کلید idempotency در دیتابیس، unique constraint، یا deduplication با `Nats-Msg-Id` در JetStream سمت ناشر.
