+++
title = "Goroutine"
summary = "اجرای سبکی از یک تابع که runtime زبان Go مدیریت می‌کند، نه سیستم‌عامل."
category = "Go"
fa_title = "گوروتین"
related = ["channel", "mutex", "worker-pool"]
posts = ["go-goroutines-channels", "go-scheduler-gc-internals", "net-sockets-tcp-from-scratch", "node-worker-threads-cluster", "node-vs-go-when-to-use"]
+++

goroutine با کلیدواژه‌ی `go` شروع می‌شود. stack اولیه‌اش فقط چند کیلوبایت است و در صورت نیاز بزرگ می‌شود، برای همین می‌شود صدها هزار تا از آن‌ها داشت. scheduler زبان Go آن‌ها را روی تعداد کمتری thread سیستم‌عامل پخش می‌کند.

```go
go func() {
	fmt.Println("runs concurrently")
}()
```

goroutine مقدار برنمی‌گرداند؛ برای ارتباط از [channel](/fa/glossary/channel/) یا حافظه‌ی مشترکِ محافظت‌شده با [mutex](/fa/glossary/mutex/) استفاده کنید.
