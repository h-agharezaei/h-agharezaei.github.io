+++
title = "Quicksort"
summary = "Pick a pivot, partition the slice around it, then sort both sides recursively; O(n log n) on average, in place."
category = "Algorithms"
related = ["merge-sort", "heap-sort", "stable-sort", "big-o"]
posts = ["algo-sorting"]
+++

Quicksort picks a **pivot**, moves smaller items to its left and larger to its right, then sorts each side. It needs no extra array, but a bad pivot (for example always the first item on sorted input) degrades it to O(n^2). Median-of-three pivots and an insertion-sort cutoff for small ranges are the usual guards. It is not stable.
