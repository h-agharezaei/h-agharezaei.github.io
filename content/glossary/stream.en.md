+++
title = "Stream"
summary = "An object that moves data in chunks, so a program never needs the whole thing in memory."
category = "Node.js"
related = ["backpressure", "high-water-mark", "event-loop"]
posts = ["node-streams-backpressure"]
+++

A stream is a source or a destination of data that is processed piece by piece. Node.js has four kinds: Readable, Writable, Duplex and Transform. Streams are connected with `pipeline`, and a slow consumer is protected by [backpressure](/glossary/backpressure/).
