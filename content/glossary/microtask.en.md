+++
title = "Microtask"
summary = "A small job (promise callback, queueMicrotask) that runs right after the current code, before the event loop continues."
category = "Node.js"
related = ["event-loop"]
posts = ["node-event-loop"]
+++

The microtask queue is drained completely after each callback. A chain of microtasks that keeps adding new ones can starve timers and I/O.
