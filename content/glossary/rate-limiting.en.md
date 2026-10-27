+++
title = "Rate limiting"
summary = "Capping how many requests a client may make in a time span."
category = "Distributed"
related = ["token-bucket", "sliding-window", "load-shedding"]
posts = []
+++

Rate limiting protects a service from overload and from one noisy client. It answers allow or reject (often HTTP 429) per key, such as a client or tenant.
