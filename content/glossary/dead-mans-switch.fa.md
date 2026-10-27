+++
title = "Dead man's switch"
summary = "هشداری که وقتی سیگنال مورد انتظار نمی‌رسد فعال می‌شود."
category = "Linux"
fa_title = "dead man's switch"
related = ["cron", "heartbeat"]
posts = ["linux-scripting-cron-safely"]
+++

کار زمان‌بندی‌شده بعد از هر اجرای موفق به یک مانیتور ping می‌زند و اگر در بازه‌ی انتظار ping نرسد، مانیتور هشدار می‌دهد. این روش کارهایی را که بی‌صدا هرگز شروع نشده‌اند پیدا می‌کند، کاری که هشدار مبتنی بر لاگ نمی‌تواند.
