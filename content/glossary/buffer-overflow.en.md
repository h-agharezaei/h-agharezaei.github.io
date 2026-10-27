+++
title = "Buffer overflow"
summary = "Writing (or reading) past the end of a fixed-size buffer, corrupting neighbouring memory."
category = "Security"
related = ["memory-safety", "use-after-free"]
posts = ["sec-memory-safety-c-vs-rust"]
+++

In C, `char buf[8]` has no length check: `memset(buf, 'A', 10)` happily writes two bytes past the end. On the stack this is a stack-buffer-overflow. Fixes: pass the real size, use bounds-checked types, and run tests with [AddressSanitizer](/glossary/addresssanitizer/).
