+++
title = "Channel"
summary = "A typed conduit that goroutines use to send and receive values safely."
category = "Go"
related = ["goroutine", "worker-pool"]
posts = ["go-goroutines-channels"]
+++

A channel is created with `make(chan T)`. An unbuffered channel blocks the sender until a receiver is ready; a buffered channel (`make(chan T, n)`) blocks only when full. Closing a channel signals that no more values will be sent, and `for v := range ch` stops when it is closed.

```go
ch := make(chan int, 1)
ch <- 42
fmt.Println(<-ch)
```
