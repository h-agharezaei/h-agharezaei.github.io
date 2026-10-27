+++
title = "B-tree"
summary = "A balanced tree of fixed-size pages with sorted keys, the default index type in PostgreSQL."
category = "Databases"
related = ["database-index", "binary-search"]
posts = ["db-indexes-btree-explain", "algo-trees-bst-btree"]
+++

A lookup starts at the root page, follows one pointer per level and ends in a leaf page that holds the key. Because the tree is wide and shallow, even millions of rows need only a few page reads, which is a [binary-search](/glossary/binary-search/)-like O(log n) descent.
