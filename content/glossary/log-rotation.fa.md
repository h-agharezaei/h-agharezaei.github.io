+++
title = "Log rotation"
fa_title = "چرخش لاگ"
summary = "تغییر نام، فشرده‌سازی و حذف فایل‌های لاگ قدیمی تا لاگ بی‌نهایت بزرگ نشود."
category = "Linux"
related = ["journald", "structured-logging"]
posts = ["linux-logs-journalctl"]
+++

در Linux ابزار `logrotate` این کار را از روی فایل پیکربندی انجام می‌دهد: هر چند وقت یا در چه اندازه‌ای بچرخد و چند فایل قدیمی بماند (`rotate N`). برنامه‌ای که هنوز فایل قدیمی را باز نگه داشته به سیگنال یا `copytruncate` نیاز دارد.
