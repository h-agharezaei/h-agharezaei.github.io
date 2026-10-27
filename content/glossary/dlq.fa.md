+++
title = "Dead-letter queue"
summary = "جایی که پیام‌هایی که مدام شکست می‌خورند به آن منتقل می‌شوند تا جریان اصلی را بلاک نکنند."
category = "Messaging"
fa_title = "صف نامه‌های مرده"
related = ["jetstream", "idempotency"]
posts = ["nats-jetstream-retry-dlq", "node-nats-jetstream"]
+++

بعد از تعداد محدودی تلاش مجدد (معمولاً با backoff)، پیام مشکل‌دار همراه با اطلاعات خطا به یک stream مخصوص DLQ منتقل می‌شود. بعداً می‌شود آن را بررسی و دوباره پخش کرد، بدون از دست دادن داده و بدون متوقف کردن پیام‌های سالم.
