+++
title = "CPU-bound"
summary = "Work whose speed is limited by the processor, such as computing primes, not by waiting for I/O."
category = "Engineering"
related = ["io-bound","event-loop"]
posts = ["node-vs-go-when-to-use"]
+++

A **CPU-bound** task keeps a core busy the whole time. On a single-threaded [event loop](/glossary/event-loop/) it blocks every other request; more cores or threads are the usual remedy.
