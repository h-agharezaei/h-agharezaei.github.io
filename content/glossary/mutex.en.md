+++
title = "Mutex"
summary = "A lock that lets only one goroutine at a time touch a piece of shared state."
category = "Go"
related = ["race-condition", "goroutine"]
posts = ["go-sync-select-context", "net-sockets-tcp-from-scratch"]
+++

`sync.Mutex` protects a critical section with `Lock()` and `Unlock()`. Always pair them, usually with `defer`. `sync.RWMutex` allows many concurrent readers or a single writer. Forgetting the lock leads to a [race condition](/glossary/race-condition/).

```go
mu.Lock()
defer mu.Unlock()
count++
```
