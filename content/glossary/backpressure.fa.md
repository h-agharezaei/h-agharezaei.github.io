+++
title = "Backpressure"
summary = "سیگنالی از مصرف‌کننده‌ی کند به تولیدکننده‌ی سریع که بایستد تا بافرها بی‌حد بزرگ نشوند."
category = "Node.js"
fa_title = "بک‌پرشر"
related = ["stream", "high-water-mark"]
posts = ["node-streams-backpressure", "net-websocket"]
+++

وقتی [stream](/fa/glossary/stream/) نمی‌تواند داده را به سرعت ورودی بپذیرد، `write()` مقدار `false` برمی‌گرداند. تولیدکننده باید تا رویداد `'drain'` صبر کند. نادیده گرفتن این سیگنال باعث می‌شود حافظه با اندازه‌ی صف انباشته بزرگ شود.
