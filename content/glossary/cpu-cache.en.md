+++
title = "CPU cache"
summary = "Small, fast memory next to the CPU that holds recently used data; sequential access uses it far better than random access."
category = "Algorithms"
related = ["big-o"]
posts = ["algo-big-o-measured"]
+++

Reading main memory is slow, so the CPU keeps recent data in small caches and loads memory in cache lines. Scanning an array in order is cache-friendly; jumping around is not. [Big-O](/glossary/big-o/) ignores this, real timings do not.
