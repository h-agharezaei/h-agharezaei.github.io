+++
title = "Turing-complete"
summary = "A language that can express any computation, given enough time and memory; it needs some form of unbounded loop or recursion."
category = "Blockchain"
related = ["bitcoin-script"]
posts = ["bc-bitcoin-script-rust", "bc-evm-internals-rust"]
+++

The price is that you cannot know in general whether a program halts. [Bitcoin Script](/glossary/bitcoin-script/) avoids loops, so the cost of a script is bounded by its length.
