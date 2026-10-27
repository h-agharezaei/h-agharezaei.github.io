+++
title = "Hash table"
summary = "A structure that finds a key by computing its hash, giving O(1) lookups on average. Go's map is one."
category = "Algorithms"
related = ["big-o"]
posts = ["algo-big-o-measured", "algo-hash-tables", "algo-dynamic-programming-1"]
+++

The key is hashed to pick a bucket, so a lookup does not scan all items. The cost is a fixed hashing step on every access, which is why a tiny slice can be faster than a map. See [Big-O](/glossary/big-o/).
