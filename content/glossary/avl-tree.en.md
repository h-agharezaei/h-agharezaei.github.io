+++
title = "AVL tree"
summary = "A binary search tree that keeps the heights of every node's two subtrees within 1 of each other using rotations."
category = "Algorithms"
related = ["binary-search-tree", "tree-rotation"]
posts = ["algo-trees-bst-btree"]
+++

The balance rule bounds the height by about 1.44 log2(n+2), so every operation is O(log n) even for sorted input. It repairs imbalance after each insert or delete with [rotations](/glossary/tree-rotation/).
