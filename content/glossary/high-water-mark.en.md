+++
title = "highWaterMark"
summary = "The buffer size at which a stream starts asking producers to slow down (16 KiB by default for a Writable)."
category = "Node.js"
related = ["stream", "backpressure"]
posts = ["node-streams-backpressure"]
+++

Every [stream](/glossary/stream/) has a `highWaterMark`. When the buffered amount reaches it, `write()` returns `false`, which is the start of [backpressure](/glossary/backpressure/). It is a threshold, not a hard limit.
