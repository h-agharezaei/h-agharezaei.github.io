+++
title = "Size class"
summary = "The Go allocator rounds each request up to one of a fixed set of block sizes. That is why a slice's capacity can be larger than the growth formula alone predicts."
category = "Algorithms"
related = ["slice"]
posts = ["algo-dynamic-arrays"]
+++

The Go allocator rounds each request up to one of a fixed set of block sizes. That is why a slice's capacity can be larger than the growth formula alone predicts.
