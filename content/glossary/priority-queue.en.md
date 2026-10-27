+++
title = "Priority queue"
summary = "An abstract container where you always remove the item with the highest priority first, not the oldest."
category = "Algorithms"
related = ["binary-heap", "big-o"]
posts = ["algo-heaps-priority-queues", "algo-greedy-backtracking"]
+++

A priority queue supports `Push` and `Pop`, where `Pop` returns the most urgent item (smallest or largest key). It is an interface, not a layout; the usual implementation is a [binary heap](/glossary/binary-heap/). Equal priorities have no defined order unless you add a tie-break such as a sequence number.
