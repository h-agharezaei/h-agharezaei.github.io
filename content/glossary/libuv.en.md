+++
title = "libuv"
summary = "The C library under Node.js that provides the event loop, async I/O and a thread pool."
category = "Node.js"
related = ["event-loop", "thread-pool"]
posts = ["node-event-loop"]
+++

Node.js uses libuv to talk to the operating system without blocking the JavaScript thread. It also runs some work (files, crypto, DNS lookup) in its thread pool.
