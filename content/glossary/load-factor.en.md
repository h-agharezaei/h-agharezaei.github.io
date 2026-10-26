+++
title = "Load factor"
summary = "How full a hash table is: stored entries divided by slots. Past a threshold the table is rehashed into a bigger one."
category = "Algorithms"
related = ["hash-table", "linear-probing"]
posts = ["algo-hash-tables"]
+++

A table with 75 entries in 100 slots has a load factor of 0.75. With open addressing the average probe length grows sharply as it approaches 1, so implementations grow the table well before that.
