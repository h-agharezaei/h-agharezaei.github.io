+++
title = "Listen backlog"
summary = "اندازه‌ی صف کرنل برای اتصال‌های منتظر accept()."
category = "Networking"
fa_title = "صف backlog"
related = ["tcp", "socket"]
posts = ["net-tcp-handshake-states", "linux-networking-ip-ss-nftables"]
+++

`listen(fd, n)` به کرنل یک صف می‌دهد برای اتصال‌هایی که handshake را کامل کرده‌اند ولی هنوز با `accept()` برداشته نشده‌اند. اینکه با پُرشدن صف چه می‌شود (SYN دور ریخته می‌شود، reset یا refuse) به سیستم‌عامل بستگی دارد.
