+++
title = "Thread pool"
summary = "A fixed set of worker threads that run blocking work (files, crypto, DNS) for Node.js; default size 4."
category = "Node.js"
related = ["libuv", "event-loop"]
posts = ["node-event-loop"]
+++

The size is set with the `UV_THREADPOOL_SIZE` environment variable. Jobs beyond the pool size wait in a queue and finish in batches.
