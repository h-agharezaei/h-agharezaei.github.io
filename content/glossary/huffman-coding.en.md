+++
title = "Huffman coding"
summary = "A greedy prefix code that gives frequent symbols shorter bit strings."
category = "Algorithms"
related = ["greedy-algorithm", "priority-queue"]
posts = ["algo-greedy-backtracking"]
+++

Huffman coding repeatedly merges the two rarest symbols using a priority queue, building a binary tree whose paths are the codes. No code is a prefix of another, so the bit stream decodes unambiguously.
