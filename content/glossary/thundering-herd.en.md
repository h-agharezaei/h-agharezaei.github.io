+++
title = "Thundering herd"
summary = "Many waiting processes or threads are all woken by one event, but only one can use it, wasting work."
category = "Linux"
related = ["epoll", "socket"]
posts = ["linux-io-epoll", "ds-service-discovery-load-balancing", "linux-scripting-cron-safely"]
+++

A classic case is several workers waiting on the same listening socket. The epoll(7) man page names `EPOLLEXCLUSIVE` as a flag that limits such wake-ups; check the man page for the exact semantics.
