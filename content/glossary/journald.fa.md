+++
title = "journald"
summary = "سرویس systemd که لاگ سرویس‌ها و کرنل را در یک ژورنال ساختاریافته جمع می‌کند."
category = "Linux"
fa_title = "journald"
related = ["systemd"]
posts = ["linux-systemd-units-timers", "linux-logs-journalctl"]
+++

ژورنال را با `journalctl` می‌خوانید، مثلاً `journalctl -u myservice` برای یک واحد. سرویس فقط کافی است در stdout یا stderr بنویسد و ژورنال آن را ثبت می‌کند.
