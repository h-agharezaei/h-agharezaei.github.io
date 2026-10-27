+++
title = "Token bucket"
summary = "A limiter that refills tokens at a fixed rate and spends one per request, allowing bursts up to its capacity."
category = "Distributed"
related = ["rate-limiting", "sliding-window"]
posts = ["ds-distributed-rate-limiting"]
+++

State is two numbers: the token count and the last refill time. A leaky bucket used as a meter makes the same decisions.
