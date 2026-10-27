+++
title = "Relaxation"
summary = "Updating a vertex's distance when a route through an edge is shorter than the best known."
category = "Algorithms"
related = ["dijkstra", "bellman-ford"]
posts = ["algo-shortest-paths-dijkstra"]
+++

Updating a vertex's distance when a route through an edge is shorter than the best known.

For an edge u to v with weight w: if dist[u] + w is less than dist[v], set dist[v] to it. Dijkstra and Bellman-Ford are both built on this step.
