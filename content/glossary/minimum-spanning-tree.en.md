+++
title = "Minimum spanning tree"
summary = "The cheapest set of edges that connects every node of a weighted graph without forming a cycle."
category = "Algorithms"
related = ["union-find"]
posts = ["algo-tries-union-find"]
+++

A minimum spanning tree (MST) of a connected weighted graph with n nodes has n-1 edges, connects all nodes, has no cycle, and has the smallest total weight. Kruskal's algorithm builds it by sorting edges and adding each edge that does not close a cycle, which union-find checks.
