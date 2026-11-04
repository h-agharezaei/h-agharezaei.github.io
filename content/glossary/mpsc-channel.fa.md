+++
title = "Channel (mpsc)"
fa_title = "channel از نوع mpsc"
summary = "صفی بین thread‌ها در std::sync::mpsc: چند تولیدکننده (sender‌های clone‌شده) و یک مصرف‌کننده."
category = "Rust"
related = ["os-thread", "send-and-sync"]
posts = ["rust-concurrency-threads"]
+++

`mpsc::channel()` یک sender و یک receiver برمی‌گرداند. فرستادن مقدار را به receiver منتقل می‌کند، پس فرستنده بعدش نمی‌تواند از آن استفاده کند. حلقه‌ی receiver وقتی تمام می‌شود که همه‌ی sender‌ها، از جمله اصلی، از بین رفته باشند.
