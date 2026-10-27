+++
title = "Merge sort"
summary = "Split in half, sort each half, merge the two sorted halves; always O(n log n), stable, but needs O(n) extra memory."
category = "Algorithms"
related = ["quicksort", "heap-sort", "stable-sort", "big-o"]
posts = ["algo-sorting"]
+++

Merge sort splits the slice, sorts each half recursively and merges them by repeatedly taking the smaller front item. When two items are equal it takes the left one first, which makes it stable. The price is a temporary buffer as large as the input.
