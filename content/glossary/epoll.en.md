+++
title = "epoll"
summary = "The Linux system call family that lets one thread wait efficiently for readiness on thousands of file descriptors."
category = "Linux"
related = ["kqueue", "file-descriptor", "edge-level-triggered"]
posts = ["linux-io-epoll"]
+++

According to epoll(7), you create an epoll instance, register file descriptors with `epoll_ctl`, and wait with `epoll_wait`, which returns only the descriptors that are ready. It is Linux-only; macOS and the BSDs have kqueue.
