+++
title = "Unit file"
summary = "فایل متنی کوچکی شبیه INI که به systemd می‌گوید یک کار را چطور اجرا یا زمان‌بندی کند."
category = "Linux"
fa_title = "فایل واحد (unit file)"
related = ["systemd"]
posts = ["linux-systemd-units-timers"]
+++

نام فایل با نوع واحد تمام می‌شود: `.service` و `.timer` و `.socket` و `.target` و `.mount` و `.path`. بخش‌هایی مثل `[Unit]` و `[Service]` و `[Install]` تنظیمات را نگه می‌دارند. بعد از ویرایش باید `systemctl daemon-reload` را اجرا کنید.
