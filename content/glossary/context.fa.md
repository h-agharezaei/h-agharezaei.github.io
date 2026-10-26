+++
title = "Context"
summary = "مقداری که لغو، مهلت زمانی و داده‌های مربوط به یک درخواست را بین لایه‌ها منتقل می‌کند."
category = "Go"
fa_title = "کانتکست"
related = ["goroutine", "errgroup"]
posts = ["go-sync-select-context", "go-graceful-shutdown-workers"]
+++

`context.Context` به‌عنوان اولین آرگومان توابعی که ممکن است بلاک شوند یا طول بکشند پاس داده می‌شود. با فراخوانی cancel یا رسیدن به timeout، کانال `ctx.Done()` بسته می‌شود و هر goroutineای که به آن گوش می‌دهد می‌تواند متوقف شود و منابعش را آزاد کند.

```go
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()
```
