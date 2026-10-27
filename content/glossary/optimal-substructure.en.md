+++
title = "Optimal substructure"
summary = "An optimal answer to the whole problem is built from optimal answers to its subproblems."
category = "Algorithms"
related = ["dynamic-programming"]
posts = ["algo-dynamic-programming-1"]
+++

An optimal answer to the whole problem is built from optimal answers to its subproblems.

The cheapest path to a grid cell extends the cheaper of the paths to its two neighbours. Without this property, storing subproblem answers does not give a correct result.
