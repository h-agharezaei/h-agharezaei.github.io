+++
title = "kqueue"
summary = "The BSD and macOS event notification interface, the cousin of Linux epoll."
category = "Linux"
related = ["epoll", "file-descriptor"]
posts = ["linux-io-epoll"]
+++

`kqueue()` creates a queue and `kevent()` both registers interest and fetches ready events. Go's runtime uses it for network polling on macOS and the BSDs.
