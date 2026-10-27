+++
title = "Differential testing"
summary = "Running two implementations on the same input and flagging any difference."
category = "Security"
related = ["fuzzing", "property-based-testing"]
posts = ["sec-fuzzing"]
+++

Used with a fuzzer, it needs no expected output: if your parser and a trusted one disagree on an input, one of them has a bug.
