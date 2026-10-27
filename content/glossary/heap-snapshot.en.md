+++
title = "Heap snapshot"
summary = "A dump of every live object in the JavaScript heap with sizes and references, used to find what holds memory."
category = "Node.js"
related = ["memory-leak", "garbage-collector"]
posts = ["node-profiling-memory-shutdown"]
+++

In Node.js you write one with `v8.writeHeapSnapshot()`. The file is JSON and can be as large as the heap itself, so delete it after use.
