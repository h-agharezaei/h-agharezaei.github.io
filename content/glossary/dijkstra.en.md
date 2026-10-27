+++
title = "Dijkstra's algorithm"
summary = "Shortest paths from one source in a graph with non-negative weights, always expanding the closest unfinished vertex."
category = "Algorithms"
related = ["relaxation", "priority-queue", "bellman-ford"]
posts = ["algo-shortest-paths-dijkstra"]
+++

Shortest paths from one source in a graph with non-negative weights, always expanding the closest unfinished vertex.

It keeps a tentative distance per vertex and a priority queue. Once a vertex is popped its distance is final, which is why negative weights break it.
