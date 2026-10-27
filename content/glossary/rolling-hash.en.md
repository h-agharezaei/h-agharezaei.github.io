+++
title = "Rolling hash"
summary = "A hash of a sliding window that is updated in O(1) by removing the old character and adding the new one."
category = "Algorithms"
related = ["rabin-karp", "hash-collision"]
posts = ["algo-string-algorithms"]
+++

With base b and modulus q the update is h = ((h - old * b^(m-1)) * b + new) mod q. Equal windows always give equal hashes; different windows may too (a collision).
