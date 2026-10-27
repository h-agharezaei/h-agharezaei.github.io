+++
title = "epoll"
summary = "فراخوان‌های سیستمی Linux که به یک thread اجازه می‌دهند به‌طور کارا منتظر آماده شدن هزاران file descriptor بماند."
category = "Linux"
fa_title = "epoll"
related = ["kqueue", "file-descriptor", "edge-level-triggered"]
posts = ["linux-io-epoll"]
+++

طبق epoll(7) یک نمونه‌ی epoll می‌سازید، fileها را با `epoll_ctl` ثبت می‌کنید و با `epoll_wait` منتظر می‌مانید که فقط descriptorهای آماده را برمی‌گرداند. فقط روی Linux هست؛ macOS و BSDها kqueue دارند.
