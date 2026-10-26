+++
title = "Object mode"
summary = "گزینه‌ای در stream که هر chunk می‌تواند هر مقدار جاوااسکریپتی باشد، نه فقط بایت یا رشته."
category = "Node.js"
fa_title = "حالت شیء"
related = ["stream", "high-water-mark"]
posts = ["node-streams-backpressure"]
+++

در object mode یک [stream](/fa/glossary/stream/) مقدارهای کامل (شیء، عدد) را به‌عنوان chunk جابه‌جا می‌کند. `Readable.from(iterable)` به‌طور پیش‌فرض یک Readable در این حالت می‌سازد و [highWaterMark](/fa/glossary/high-water-mark/) در آن تعداد شیء را می‌شمارد، نه بایت.
