+++
title = "Stop-the-world"
summary = "A short pause in which the runtime stops all goroutines so that it can do work that needs a consistent view, such as parts of a GC cycle."
category = "Go"
related = ["goroutine", "garbage-collector"]
posts = ["go-scheduler-gc-internals"]
+++

Most of Go's garbage collection runs concurrently with your code, but a cycle still has brief stop-the-world phases at its start and end (the first and third clock numbers in a `gctrace` line).
