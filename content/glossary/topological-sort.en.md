+++
title = "Topological sort"
summary = "An ordering of a DAG's vertices in which every edge goes from earlier to later."
category = "Algorithms"
related = ["dag", "in-degree", "dfs"]
posts = ["algo-topological-sort"]
+++

If edge `u -> v` means "u must come before v", a topological order lists all vertices so that every edge points forward. It exists only for a [DAG](/glossary/dag/), and it is usually not unique.
