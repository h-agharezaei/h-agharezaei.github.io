+++
title = "Linked list"
summary = "A sequence of separately allocated nodes, each holding a value and a pointer to the next one (and sometimes the previous one). Cheap to splice, slow to index."
category = "Algorithms"
related = ["dynamic-array","cache-locality"]
posts = ["algo-linked-lists"]
+++

A sequence of separately allocated nodes, each holding a value and a pointer to the next one (a doubly linked list also has a pointer to the previous one). Inserting or removing next to a node you already hold is O(1), but reaching the i-th element means walking i pointers. Compare a [dynamic array](/glossary/dynamic-array/).
