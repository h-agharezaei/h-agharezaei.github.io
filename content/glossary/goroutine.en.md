+++
title = "Goroutine"
summary = "A lightweight function execution managed by the Go runtime, not the OS."
category = "Go"
related = ["channel", "mutex", "worker-pool"]
posts = ["go-goroutines-channels", "go-scheduler-gc-internals"]
+++

A goroutine is started with the `go` keyword. It begins with a small stack (a few KB) that grows on demand, so programs can run hundreds of thousands of them. The Go scheduler multiplexes goroutines onto a smaller number of OS threads.

```go
go func() {
	fmt.Println("runs concurrently")
}()
```

Goroutines do not return values directly; use a [channel](/glossary/channel/) or shared state guarded by a [mutex](/glossary/mutex/) to communicate.
