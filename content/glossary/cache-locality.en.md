+++
title = "Cache locality"
summary = "Data that is used together and sits close together in memory is cheaper to read, because the CPU loads memory in cache lines and prefetches sequential access."
category = "Algorithms"
related = ["linked-list","dynamic-array"]
posts = ["algo-linked-lists"]
+++

Data that is used together and sits close together in memory is cheaper to read, because the CPU fetches memory in small blocks (cache lines) and tends to prefetch sequential access. Arrays have good locality; pointer-chasing structures such as a [linked list](/glossary/linked-list/) can have poor locality.
