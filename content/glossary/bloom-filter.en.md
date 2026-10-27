+++
title = "Bloom filter"
summary = "A bit-array structure that answers 'definitely not present' or 'maybe present', never a false negative."
category = "Algorithms"
related = ["hash-table","consistent-hashing"]
posts = ["algo-bloom-filter-consistent-hashing"]
+++

A Bloom filter sets k bits per inserted key and checks the same k bits on lookup. If any bit is 0 the key was never added; if all are 1 it may be a false positive. It uses far less memory than a set but cannot delete (a counting variant can). See [Hash table](/glossary/hash-table/).
