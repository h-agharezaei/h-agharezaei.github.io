+++
title = "Goroutine leak"
summary = "A goroutine that is stuck forever (usually blocked on a channel) and so never frees its memory."
category = "Go"
related = ["goroutine", "channel", "context"]
posts = ["go-concurrency-patterns"]
+++

A goroutine that waits on a channel nobody will ever read or write stays alive until the program ends. Calling the leaky code again and again adds one stuck goroutine per call, and `runtime.NumGoroutine()` keeps growing. The usual fixes are a buffered channel for the last result and a [context](/glossary/context/) that tells the work to stop.
