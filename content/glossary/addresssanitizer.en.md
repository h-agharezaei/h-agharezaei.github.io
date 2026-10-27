+++
title = "AddressSanitizer"
summary = "A compiler-inserted runtime checker (ASan) that reports out-of-bounds access, use-after-free and double free."
category = "Security"
related = ["memory-safety", "buffer-overflow", "fuzzing"]
posts = ["sec-memory-safety-c-vs-rust", "sec-fuzzing"]
+++

Compile with `-fsanitize=address` and the program stops at the first bad access with a report naming the error type and the line. It slows the program down and is meant for tests and CI, not production. [Fuzzing](/glossary/fuzzing/) is often run with it.
