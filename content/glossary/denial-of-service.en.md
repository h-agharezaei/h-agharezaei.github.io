+++
title = "Denial of service"
summary = "An attack or accident that makes a service unavailable by exhausting a resource such as memory, connections or CPU."
category = "Security"
related = ["slowloris", "stride"]
posts = ["sec-threat-modeling-stride", "sec-fuzzing"]
+++

Typical defences are limits (body size, rate, concurrency) and timeouts, so no single client can hold a resource for free.
