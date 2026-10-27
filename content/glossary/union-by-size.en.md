+++
title = "Union by size"
summary = "When merging two trees, attach the smaller under the larger root so trees stay shallow."
category = "Algorithms"
related = ["union-find", "path-compression"]
posts = ["algo-tries-union-find"]
+++

Union by size keeps a size per root and always hangs the smaller tree under the larger one. A node's depth then grows only when its tree at least doubles, so depth stays at most log2 n. Union by rank is the same idea using an estimate of height.
