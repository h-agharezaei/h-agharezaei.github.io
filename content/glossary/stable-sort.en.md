+++
title = "Stable sort"
summary = "A sort that keeps equal elements in their original relative order."
category = "Algorithms"
related = ["merge-sort", "quicksort"]
posts = ["algo-sorting"]
+++

If you sort orders by city and two orders share a city, a stable sort keeps them in the order they arrived. That is what makes "sort by date, then by city" work. Merge sort is stable; plain quicksort and heap sort are not. In Go, `sort.Stable` and `slices.SortStableFunc` guarantee it.
