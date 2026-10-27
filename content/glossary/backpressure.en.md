+++
title = "Backpressure"
summary = "A signal from a slow consumer telling a fast producer to pause so buffers do not grow without limit."
category = "Node.js"
related = ["stream", "high-water-mark"]
posts = ["node-streams-backpressure", "net-websocket", "py-asyncio", "ds-circuit-breaker-bulkhead"]
+++

When a [stream](/glossary/stream/) cannot accept data as fast as it arrives, `write()` returns `false`. The producer should stop until the `'drain'` event fires. Ignoring the signal makes memory grow with the size of the backlog.
