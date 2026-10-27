+++
title = "Mutex"
summary = "قفلی که در هر لحظه فقط به یک goroutine اجازه‌ی دسترسی به یک حافظه‌ی مشترک را می‌دهد."
category = "Go"
fa_title = "میوتکس"
related = ["race-condition", "goroutine"]
posts = ["go-sync-select-context", "net-sockets-tcp-from-scratch"]
+++

`sync.Mutex` یک بخش بحرانی را با `Lock()` و `Unlock()` محافظت می‌کند. این دو را همیشه جفت کنید، معمولاً با `defer`. `sync.RWMutex` اجازه می‌دهد چند خواننده هم‌زمان باشند یا فقط یک نویسنده. فراموش کردن قفل به [race condition](/fa/glossary/race-condition/) می‌انجامد.

```go
mu.Lock()
defer mu.Unlock()
count++
```
