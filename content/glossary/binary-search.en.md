+++
title = "Binary search"
summary = "A search that discards half of the remaining range at every step, in O(log n)."
category = "Algorithms"
related = ["git-bisect"]
posts = ["git-bisect", "algo-big-o-measured", "db-indexes-btree-explain"]
+++

Look at the middle element, decide which half can still contain the answer, and repeat. 1000 items need at most about 10 steps. [git bisect](/glossary/git-bisect/) applies it to commit history.
