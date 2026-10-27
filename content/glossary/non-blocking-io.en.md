+++
title = "Non-blocking I/O"
summary = "A mode where read, write and accept return immediately with an error such as EAGAIN instead of making the thread wait."
category = "Linux"
related = ["epoll", "file-descriptor"]
posts = ["linux-io-epoll"]
+++

A descriptor is switched to this mode with the `O_NONBLOCK` flag (`fcntl(2)`). It is normally combined with a readiness API such as epoll or kqueue, which tells you when trying again will succeed.
