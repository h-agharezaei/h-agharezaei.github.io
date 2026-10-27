+++
title = "KMP algorithm"
summary = "String search that precomputes a failure function so the text pointer never moves backwards."
category = "Algorithms"
related = ["rolling-hash", "rabin-karp"]
posts = ["algo-string-algorithms"]
+++

KMP (Knuth–Morris–Pratt) searches a text in O(n + m) comparisons. After a mismatch it uses the pattern's own prefix structure to decide how much of the match to keep.
