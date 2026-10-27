+++
title = "A*"
summary = "Dijkstra guided by a heuristic estimate of the remaining cost, so fewer nodes are expanded."
category = "Algorithms"
related = ["dijkstra", "priority-queue"]
posts = ["algo-shortest-paths-dijkstra"]
+++

Dijkstra guided by a heuristic estimate of the remaining cost, so fewer nodes are expanded.

The heap is ordered by cost so far plus the estimate. If the estimate never overestimates (it is admissible), the path found is still optimal.
