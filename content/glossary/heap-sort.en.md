+++
title = "Heap sort"
summary = "Build a max-heap in place, then repeatedly swap the root to the end and sift down; O(n log n), no extra memory, not stable."
category = "Algorithms"
related = ["binary-heap", "heapify", "quicksort", "merge-sort"]
posts = ["algo-sorting"]
+++

Heap sort turns the slice into a max-heap with [heapify](/glossary/heapify/), then swaps the largest item (the root) to the end of the shrinking heap and restores the heap. It has a guaranteed O(n log n) bound and needs no buffer, but it jumps around memory and usually does more comparisons than quicksort or merge sort.
