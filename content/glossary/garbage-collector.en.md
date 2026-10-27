+++
title = "Garbage collector"
summary = "The runtime part that frees objects nothing can reach any more."
category = "Node.js"
related = ["memory-leak"]
posts = ["node-profiling-memory-shutdown"]
+++

V8 runs short scavenges for young objects and slower mark-compact passes for the old generation; `--trace-gc` prints each one.
