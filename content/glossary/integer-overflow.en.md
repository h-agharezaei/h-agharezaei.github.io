+++
title = "Integer overflow"
summary = "A result too large for its integer type; in Go it wraps around silently."
category = "Algorithms"
related = ["binary-search"]
posts = ["algo-binary-search-invariants", "sec-fuzzing", "sec-memory-safety-c-vs-rust"]
+++

When an arithmetic result does not fit in the integer type. In Go, signed integers wrap around silently, so a sum of two large positive numbers can become negative.
