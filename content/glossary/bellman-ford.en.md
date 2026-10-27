+++
title = "Bellman-Ford"
summary = "Shortest paths that allow negative weights by relaxing every edge up to V times, at O(V·E)."
category = "Algorithms"
related = ["relaxation", "negative-cycle", "dijkstra"]
posts = ["algo-shortest-paths-dijkstra"]
+++

Shortest paths that allow negative weights by relaxing every edge up to V times, at O(V·E).

If a V-th round still improves a distance, a negative cycle is reachable from the source.
