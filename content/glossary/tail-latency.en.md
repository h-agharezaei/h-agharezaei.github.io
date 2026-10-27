+++
title = "Tail latency"
summary = "The slowest few percent of requests (p99, p999), which dominate what users feel in fan-out systems."
category = "Distributed"
related = ["percentile", "fan-out", "utilization"]
posts = ["ds-capacity-estimation"]
+++

If one request makes 100 calls and each is slow 1% of the time, 1 - 0.99^100 ≈ 63% of requests see at least one slow call.
