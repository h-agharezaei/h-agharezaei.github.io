+++
title = "Heap (memory)"
summary = "The region of memory for data whose size is dynamic or unknown at compile time."
category = "Rust"
related = ["stack-memory", "ownership", "garbage-collector"]
posts = ["rust-ownership"]
+++

You ask the system for space, get an address back and must release it later. In Rust the owner of the value releases it when it goes out of scope; in Go a garbage collector does it. Not to be confused with the heap data structure used for priority queues.
