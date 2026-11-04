+++
title = "singleflight"
summary = "A Go helper (golang.org/x/sync/singleflight) that lets concurrent calls with the same key share one execution and its result."
category = "Go"
related = ["rate-limiting", "ttl"]
posts = ["go-rate-limiting-caching"]
+++

`Group.Do(key, fn)` runs `fn` once for a key; callers that arrive while it is running wait and receive the same result and error. It is the usual cure for a [cache stampede](/glossary/cache-stampede/).
