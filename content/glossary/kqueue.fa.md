+++
title = "kqueue"
summary = "رابط اعلان رویداد در BSD و macOS، هم‌خانواده‌ی epoll در Linux."
category = "Linux"
fa_title = "kqueue"
related = ["epoll", "file-descriptor"]
posts = ["linux-io-epoll"]
+++

`kqueue()` یک صف می‌سازد و `kevent()` هم علاقه‌مندی را ثبت می‌کند و هم رویدادهای آماده را می‌گیرد. runtime در Go روی macOS و BSDها از آن برای poll شبکه استفاده می‌کند.
