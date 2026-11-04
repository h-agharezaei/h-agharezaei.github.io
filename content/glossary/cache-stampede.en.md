+++
title = "Cache stampede"
summary = "When a hot cache entry expires and many concurrent requests all miss and hit the backend at once."
category = "Go"
related = ["rate-limiting", "ttl"]
posts = ["go-rate-limiting-caching"]
+++

If a popular key expires, every request that arrives before it is reloaded misses the cache and calls the database. With 50 concurrent requests that is 50 identical queries instead of one. Request coalescing (see [singleflight](/glossary/singleflight/)) avoids it.
