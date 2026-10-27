+++
title = "Consistent hashing"
summary = "A key-to-node mapping where removing a node moves only that node's keys."
category = "Networking"
related = ["load-balancer", "hash-table"]
posts = ["net-load-balancer-l4-l7", "algo-bloom-filter-consistent-hashing"]
+++

Nodes are placed on a hash ring (usually many points each) and a key goes to the next point clockwise. Compared with `hash % N`, removing a node remaps only the keys that lived on it.
