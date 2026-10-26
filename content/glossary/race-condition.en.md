+++
title = "Race condition"
summary = "A bug where the result depends on the unsynchronized timing of concurrent accesses."
category = "Go"
related = ["mutex", "goroutine"]
posts = ["go-sync-select-context", "go-concurrency-patterns"]
+++

A data race happens when two goroutines access the same variable at the same time and at least one writes. The outcome is undefined and often appears only under load. Go ships a detector: run tests or the program with `go test -race` or `go run -race`.
