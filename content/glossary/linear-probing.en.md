+++
title = "Linear probing"
summary = "Open addressing strategy: if the slot is taken, try the next one, and the next, until a free slot or the key is found."
category = "Algorithms"
related = ["hash-table", "tombstone", "load-factor"]
posts = ["algo-hash-tables"]
+++

It is cache-friendly because neighbouring slots sit next to each other in memory, but keys that collide form clusters that make later lookups longer.
