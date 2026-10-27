+++
title = "SIGTERM"
summary = "The polite signal that asks a process to stop, which it may catch to clean up first."
category = "Node.js"
related = ["graceful-shutdown"]
posts = ["node-profiling-memory-shutdown", "linux-processes-signals"]
+++

Orchestrators send it before the unstoppable SIGKILL. In Node.js you handle it with `process.once('SIGTERM', ...)`.
