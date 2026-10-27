+++
title = "Negative cycle"
summary = "A cycle whose edge weights sum to less than zero, so going around it forever keeps lowering the cost."
category = "Algorithms"
related = ["bellman-ford"]
posts = ["algo-shortest-paths-dijkstra"]
+++

A cycle whose edge weights sum to less than zero, so going around it forever keeps lowering the cost.

When one is reachable, no shortest path exists. Bellman-Ford detects it.
