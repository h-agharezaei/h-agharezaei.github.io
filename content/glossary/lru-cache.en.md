+++
title = "LRU cache"
summary = "A cache with a fixed size that, when full, evicts the least recently used entry. Usually a map plus a doubly linked list."
category = "Algorithms"
related = ["linked-list"]
posts = ["algo-linked-lists"]
+++

A cache with a fixed size that evicts the least recently used entry when it is full. The usual build is a hash map from key to list node plus a doubly [linked list](/glossary/linked-list/) ordered by recency, so lookup, move-to-front and eviction are all O(1).
