+++
title = "Context"
summary = "A value carrying cancellation, deadlines and request-scoped data across API boundaries."
category = "Go"
related = ["goroutine", "errgroup"]
posts = ["go-sync-select-context", "go-graceful-shutdown-workers"]
+++

`context.Context` is passed as the first argument of functions that may block or take long. Calling the cancel function, or hitting a timeout, closes `ctx.Done()` so every goroutine listening on it can stop and release resources.

```go
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()
```
