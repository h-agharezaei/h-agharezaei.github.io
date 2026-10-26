+++
title = "errgroup"
summary = "A `golang.org/x/sync` helper that runs goroutines together and cancels the rest on the first error."
category = "Go"
related = ["context", "worker-pool"]
posts = ["go-concurrency-patterns"]
+++

`errgroup.WithContext` returns a group and a derived [context](/glossary/context/). `g.Go(fn)` starts a goroutine; `g.Wait()` blocks until all finish and returns the first non-nil error. `g.SetLimit(n)` bounds concurrency without writing a [worker pool](/glossary/worker-pool/) by hand.
