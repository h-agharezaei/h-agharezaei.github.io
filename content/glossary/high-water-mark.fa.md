+++
title = "highWaterMark"
summary = "اندازه‌ی بافری که از آن به بعد stream از تولیدکننده می‌خواهد آهسته‌تر شود (برای Writable پیش‌فرض 16 KiB)."
category = "Node.js"
fa_title = "highWaterMark"
related = ["stream", "backpressure"]
posts = ["node-streams-backpressure"]
+++

هر [stream](/fa/glossary/stream/) یک `highWaterMark` دارد. وقتی مقدار بافرشده به آن برسد، `write()` مقدار `false` برمی‌گرداند و [backpressure](/fa/glossary/backpressure/) شروع می‌شود. این یک آستانه است، نه سقف سخت.
