+++
title = "Hash collision"
summary = "Two different keys that map to the same slot of a hash table."
category = "Algorithms"
related = ["hash-table", "load-factor"]
posts = ["algo-hash-tables"]
+++

Collisions are unavoidable, so every hash table needs a strategy: chaining keeps a list per slot, open addressing looks for another slot.
