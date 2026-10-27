+++
title = "Semaphore"
summary = "A counter-based primitive that lets at most N holders in at once; the rest wait."
category = "Python"
related = ["coroutine", "queue"]
posts = ["py-asyncio", "ds-circuit-breaker-bulkhead"]
+++

A counter-based primitive that lets at most N holders in at once; the rest wait. Use it to cap concurrency, for example at most 3 requests in flight. In asyncio it is `asyncio.Semaphore(3)` used with `async with`.
