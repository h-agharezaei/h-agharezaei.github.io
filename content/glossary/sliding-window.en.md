+++
title = "Sliding window counter"
summary = "An approximate limiter that weights the previous fixed window by how much of it still overlaps the last interval."
category = "Distributed"
related = ["rate-limiting", "token-bucket"]
posts = ["ds-distributed-rate-limiting"]
+++

The estimate is previous_count * (1 - elapsed/window) + current_count. It needs a few numbers per key, unlike a sliding log that stores every timestamp.
