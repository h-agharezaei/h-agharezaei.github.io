+++
title = "SharedArrayBuffer"
summary = "A memory block visible to several threads at once, used with Atomics."
category = "Node.js"
related = ["worker-threads", "race-condition"]
posts = ["node-worker-threads-cluster"]
+++

A `SharedArrayBuffer` is not copied between worker threads: all of them see the same bytes. Plain reads and writes on it can race, so use `Atomics` (for example `Atomics.add`) for indivisible updates.
