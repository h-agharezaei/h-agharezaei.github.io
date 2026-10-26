+++
title = "Ring buffer"
summary = "A fixed array with a head index and a count where positions wrap around with modulo, so removing from the front never shifts elements. When full it can double (copying once) to keep amortized O(1) pushes."
category = "Algorithms"
related = ["queue", "deque", "dynamic-array"]
posts = ["algo-stacks-queues-deques"]
+++

A fixed array with a head index and a count where positions wrap around with modulo, so removing from the front never shifts elements. When full it can double (copying once) to keep amortized O(1) pushes.
