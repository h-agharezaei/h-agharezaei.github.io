+++
title = "AbortController"
summary = "A standard object that signals cancellation to async operations through its AbortSignal."
category = "Node.js"
related = ["promise"]
posts = ["node-promises-async-await"]
+++

You pass `controller.signal` to an API that supports it (timers, `fetch`, `fs`...). Calling `controller.abort()` makes the operation reject with an `AbortError`. `AbortSignal.timeout(ms)` makes a signal that aborts by itself.
