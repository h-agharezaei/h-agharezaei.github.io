+++
title = "Non-blocking I/O"
summary = "حالتی که read و write و accept به‌جای منتظر نگه داشتن thread، فوراً با خطایی مثل EAGAIN برمی‌گردند."
category = "Linux"
fa_title = "I/O غیرمسدودکننده"
related = ["epoll", "file-descriptor"]
posts = ["linux-io-epoll"]
+++

descriptor با پرچم `O_NONBLOCK` (`fcntl(2)`) به این حالت می‌رود. معمولاً با API آمادگی مثل epoll یا kqueue ترکیب می‌شود که می‌گوید کِی تلاش دوباره موفق است.
