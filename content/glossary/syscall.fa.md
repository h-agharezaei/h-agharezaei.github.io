+++
title = 'System call'
fa_title = 'فراخوان سیستمی'
summary = 'درخواست یک برنامه از کرنل، مثل open یا read؛ ابزارهایی مثل strace آن‌ها را نشان می‌دهند.'
category = 'Linux'
related = ["process", "file-descriptor"]
posts = ["linux-proc-observability"]
+++

**System call** راه برنامه برای خواستن کار از کرنل است: باز کردن فایل، خواندن، ساخت پروسه. ابزار `strace` در Linux فهرست آن‌ها را برای یک پروسه نشان می‌دهد.
