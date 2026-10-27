+++
title = "Rabin–Karp"
summary = "String search that compares hashes of windows first and verifies real text only when hashes are equal."
category = "Algorithms"
related = ["rolling-hash", "kmp-algorithm", "hash-collision"]
posts = ["algo-string-algorithms"]
+++

Rabin–Karp slides a window over the text, updating a rolling hash in O(1). A hash match can be a collision, so it must be verified. It extends naturally to many patterns of the same length.
