+++
title = "Union-find"
summary = "A structure that tracks which elements belong to the same group, with Find (which group?) and Union (merge two groups)."
category = "Algorithms"
related = ["path-compression", "union-by-size", "amortized-analysis"]
posts = ["algo-tries-union-find", "algo-greedy-backtracking"]
+++

Union-find, also called a disjoint set, keeps elements in groups that never overlap. `Find(x)` returns the representative of x's group and `Union(a, b)` merges two groups. With path compression and union by size, a sequence of operations is almost linear in total, according to the literature.
