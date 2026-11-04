+++
title = "Fan-out / fan-in"
summary = "Splitting work across many goroutines (fan-out) and gathering their results into one place (fan-in)."
category = "Go"
related = ["worker-pool", "goroutine", "channel"]
posts = ["go-concurrency-patterns"]
+++

Fan-out means several goroutines read jobs from the same [channel](/glossary/channel/), so the work is shared among them. Fan-in means their results all flow into one channel that a single reader consumes. A [worker pool](/glossary/worker-pool/) is the common example of both together.
