+++
title = "Level-triggered and edge-triggered"
summary = "Two ways a readiness API reports events: while data is still waiting (level) or only when new data arrives (edge)."
category = "Linux"
related = ["epoll", "kqueue", "non-blocking-io"]
posts = ["linux-io-epoll"]
+++

Level-triggered reports a descriptor as ready on every wait while unread data remains. Edge-triggered reports it once per change, so you must read until EAGAIN or you can stall. In kqueue the edge-like behaviour comes from `EV_CLEAR`.
