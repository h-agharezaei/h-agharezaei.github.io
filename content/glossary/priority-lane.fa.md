+++
title = "Priority lane"
summary = "یک صف یا consumer جدا برای هر اولویت که به ترتیب سخت‌گیرانه سرویس می‌گیرد تا پیام فوری پشت یک backlog نماند."
category = "Distributed"
fa_title = "priority lane"
related = ["jetstream", "fan-out"]
posts = ["ds-case-studies"]
+++

پیام‌ها به subjectهایی مثل `notify.high.sms` و `notify.low.sms` می‌روند و worker اول از consumer اولویت بالا می‌پرسد. خطر آن گرسنگی لاین پایین است؛ بخشی از ظرفیت را برایش نگه دارید.
