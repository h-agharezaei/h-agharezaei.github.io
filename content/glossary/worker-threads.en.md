+++
title = "Worker threads"
summary = "Threads inside one Node process, each with its own event loop and heap, for CPU-bound work."
category = "Node.js"
related = ["event-loop", "worker-pool", "shared-array-buffer"]
posts = ["node-worker-threads-cluster"]
+++

Node.js's `worker_threads` module starts extra threads in the same process. Each has its own event loop and memory; data moves by copying with `postMessage`, by transfer, or through a [SharedArrayBuffer](/glossary/shared-array-buffer/).
