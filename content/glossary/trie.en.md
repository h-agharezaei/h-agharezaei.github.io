+++
title = "Trie"
summary = "A tree where each edge is one character, so words that share a prefix share a path. Lookup cost depends on the word length, not on the number of words."
category = "Algorithms"
related = ["hash-table"]
posts = ["algo-tries-union-find"]
+++

A trie (prefix tree) stores a set of strings so that each node is a prefix and each edge adds one character. Insert, search and prefix queries walk one path of length equal to the word. It makes autocomplete natural: find the prefix node, then list what lies below it.
