+++
title = "Gray failure"
summary = "A node that is not dead but so slow or flaky that it harms the system while still looking alive."
category = "Distributed"
related = ["failure-detector", "partial-failure"]
posts = ["ds-why-distributed-is-hard"]
+++

Health checks and heartbeats may pass while real requests time out. In my experience this is harder to handle than a clean crash.
