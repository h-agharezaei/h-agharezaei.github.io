+++
title = "Worker pool"
summary = "A fixed number of goroutines consuming jobs from a shared queue."
category = "Go"
related = ["goroutine", "channel", "errgroup"]
posts = ["go-concurrency-patterns", "go-graceful-shutdown-workers", "node-worker-threads-cluster", "py-gil-threading"]
+++

Instead of spawning one goroutine per job, start N workers that read from a jobs [channel](/glossary/channel/). This bounds memory and downstream load. The producer closes the jobs channel when done; workers exit when `range` ends.
