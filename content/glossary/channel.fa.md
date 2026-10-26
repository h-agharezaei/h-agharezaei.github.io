+++
title = "Channel"
summary = "مجرایی با نوع مشخص که goroutineها برای ارسال و دریافت امن مقدار از آن استفاده می‌کنند."
category = "Go"
fa_title = "کانال"
related = ["goroutine", "worker-pool"]
posts = ["go-goroutines-channels"]
+++

channel با `make(chan T)` ساخته می‌شود. channel بدون بافر فرستنده را تا آماده شدن گیرنده بلاک می‌کند؛ channel بافردار (`make(chan T, n)`) فقط وقتی پر شود بلاک می‌کند. بستن channel یعنی دیگر مقداری فرستاده نمی‌شود و `for v := range ch` با بسته شدن آن تمام می‌شود.

```go
ch := make(chan int, 1)
ch <- 42
fmt.Println(<-ch)
```
