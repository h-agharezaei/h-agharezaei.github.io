+++
title = "Coverage-guided fuzzing"
summary = "Fuzzing that keeps and mutates inputs which reach new code paths."
category = "Security"
related = ["fuzzing", "code-coverage"]
posts = ["sec-fuzzing"]
+++

The fuzzer instruments the program, and an input that executes a branch no earlier input reached is kept as "interesting" and mutated further. This steers the search deep into the parser instead of guessing blindly.
