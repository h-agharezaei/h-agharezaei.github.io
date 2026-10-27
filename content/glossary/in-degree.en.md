+++
title = "In-degree"
summary = "The number of edges pointing into a vertex; in dependency graphs, how many prerequisites it still waits for."
category = "Algorithms"
related = ["topological-sort", "dag"]
posts = ["algo-topological-sort"]
+++

Kahn's algorithm keeps an in-degree counter per vertex. A vertex with in-degree 0 has no unfinished prerequisites and is ready.
