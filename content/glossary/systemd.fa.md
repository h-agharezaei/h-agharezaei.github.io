+++
title = "systemd"
summary = "اولین پروسه و مدیر سرویس در بیشتر توزیع‌های Linux (PID 1)."
category = "Linux"
fa_title = "systemd"
related = ["unit-file", "cron"]
posts = ["linux-systemd-units-timers"]
+++

systemd بقیه‌ی پروسه‌ها را بالا می‌آورد، نظارت می‌کند، در صورت تنظیم دوباره راه می‌اندازد و به ترتیب متوقف می‌کند. واحد (unit) پایه‌ی کارش است که با یک unit file توصیف می‌شود. ابزارهای `systemctl` و `journalctl` و `systemd-analyze` هم از آن هستند.
