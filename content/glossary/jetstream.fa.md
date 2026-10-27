+++
title = "JetStream"
summary = "لایه‌ی ماندگاری NATS: streamهایی که پیام را ذخیره می‌کنند و consumerهایی که آن‌ها را می‌خوانند."
category = "Messaging"
fa_title = "جت‌استریم"
related = ["durable-consumer", "dlq", "idempotency"]
posts = ["nats-jetstream-go", "nats-jetstream-production", "node-nats-jetstream", "eng-adr-documentation"]
+++

NATS هسته‌ای fire-and-forget است. JetStream ذخیره‌سازی ماندگار، acknowledgement، replay و تضمین تحویل اضافه می‌کند. یک *stream* subjectها را ضبط می‌کند و یک [durable consumer](/fa/glossary/durable-consumer/) پیشرفت خواندن را نگه می‌دارد.
