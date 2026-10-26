+++
title = "Object mode"
summary = "A stream option where each chunk is any JavaScript value instead of bytes or a string."
category = "Node.js"
related = ["stream", "high-water-mark"]
posts = ["node-streams-backpressure"]
+++

In object mode a [stream](/glossary/stream/) passes whole values (objects, numbers) as chunks. `Readable.from(iterable)` creates an object-mode Readable by default, and the [highWaterMark](/glossary/high-water-mark/) then counts objects, not bytes.
