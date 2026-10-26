+++
title = "Heapify"
summary = "Turning an unordered slice into a heap in place in O(n), by sifting down from the last parent to the root."
category = "Algorithms"
related = ["binary-heap", "big-o"]
posts = ["algo-heaps-priority-queues"]
+++

Heapify starts at index `n/2-1` and sifts each node down. Most nodes are near the leaves and move very little, so the total work is O(n), cheaper in the worst case than pushing n items one by one (O(n log n)). See [Binary heap](/glossary/binary-heap/).
