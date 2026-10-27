+++
title = "Path compression"
summary = "During Find, point every node on the path straight at the root so later Finds are shorter."
category = "Algorithms"
related = ["union-find", "union-by-size"]
posts = ["algo-tries-union-find"]
+++

After `Find(x)` discovers the root, path compression rewrites the parent of every node it passed to be that root. The work is paid once and makes the next Finds on the same nodes one hop long.
