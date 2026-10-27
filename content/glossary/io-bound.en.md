+++
title = "I/O-bound"
summary = "Work that spends most of its time waiting for the network or disk rather than computing."
category = "Engineering"
related = ["cpu-bound","event-loop"]
posts = ["node-vs-go-when-to-use"]
+++

An **I/O-bound** task is mostly waiting, for example for an upstream HTTP call. An [event loop](/glossary/event-loop/) or many [goroutines](/glossary/goroutine/) can overlap thousands of such waits cheaply.
