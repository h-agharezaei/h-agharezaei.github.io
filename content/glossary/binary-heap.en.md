+++
title = "Binary heap"
summary = "A complete binary tree stored in a slice where every parent is not larger than its children; the minimum is always at index 0."
category = "Algorithms"
related = ["priority-queue", "heapify", "dynamic-array", "big-o"]
posts = ["algo-heaps-priority-queues"]
+++

In a min-heap stored in a slice, the children of index `i` are `2i+1` and `2i+2`, and the parent is `(i-1)/2`. `Push` appends and sifts up; `Pop` moves the last item to the root and sifts down. Both are O(log n), `Peek` is O(1). Siblings are not ordered, so a heap is not a sorted list.
