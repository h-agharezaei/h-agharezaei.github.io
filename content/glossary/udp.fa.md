+++
title = "UDP"
summary = "پروتکل datagram بدون اتصال روی IP، بدون تضمین تحویل."
category = "Networking"
fa_title = "یو‌دی‌پی"
related = ["tcp", "dns"]
posts = ["net-dns-in-practice"]
+++

UDP فقط پورت و checksum را به IP اضافه می‌کند و datagramها مستقل فرستاده می‌شوند. چیزی برایتان دوباره ارسال نمی‌شود و برنامه خودش با گم‌شدن کنار می‌آید؛ برای پروتکل‌های کوچک درخواست/پاسخ مثل DNS مناسب است.
