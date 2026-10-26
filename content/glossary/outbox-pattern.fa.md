+++
title = "Outbox pattern"
summary = "نوشتن رویداد در یک جدول دیتابیس و در همان تراکنش تغییر داده، و انتشار آن در مرحله‌ی بعد."
category = "Messaging"
fa_title = "الگوی outbox"
related = ["idempotency", "jetstream"]
posts = ["go-outbox-pattern-nats"]
+++

این الگو مشکل dual-write را حذف می‌کند: هیچ‌وقت نمی‌شود ردیف commit شود ولی رویداد گم شود یا برعکس. یک relay جدول outbox را می‌خواند و به broker منتشر می‌کند؛ پس تحویل at-least-once است و consumerها باید [idempotent](/fa/glossary/idempotency/) باشند.
