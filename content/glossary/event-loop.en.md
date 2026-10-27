+++
title = "Event loop"
summary = "The loop that lets single-threaded JavaScript handle many waiting operations by running callbacks when they are ready."
category = "Node.js"
related = ["libuv", "microtask", "thread-pool"]
posts = ["node-event-loop", "py-gil-threading", "py-asyncio"]
+++

The event loop repeatedly goes through phases (timers, poll, check, close) and runs the callbacks that are ready. Your JavaScript runs on one thread, so a long synchronous task delays everything else.
