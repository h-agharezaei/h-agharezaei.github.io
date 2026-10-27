+++
title = "Memory leak"
summary = "Memory that is no longer needed but is still reachable, so the garbage collector cannot free it."
category = "Node.js"
related = ["garbage-collector", "heap-snapshot"]
posts = ["node-profiling-memory-shutdown"]
+++

The classic case is a module-level `Map` or array that grows with every request and is never trimmed.
