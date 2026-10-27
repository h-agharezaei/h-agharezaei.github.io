+++
title = 'SIGKILL'
summary = 'کشتن اجباری (سیگنال ۹)؛ نه گرفته می‌شود نه نادیده، پس هیچ کد پاک‌سازی اجرا نمی‌شود.'
category = 'Linux'
fa_title = 'SIGKILL'
related = ["signal", "sigterm"]
posts = ["linux-processes-signals", "linux-systemd-units-timers", "linux-memory-page-cache-oom"]
+++

کشتن اجباری (سیگنال ۹)؛ نه گرفته می‌شود نه نادیده، پس هیچ کد پاک‌سازی اجرا نمی‌شود. فقط بعد از شکست SIGTERM استفاده کنید. شل کد خروج ۱۳۷ (128+9) گزارش می‌کند.
