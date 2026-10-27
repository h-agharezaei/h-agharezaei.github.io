+++
title = "Table rewrite"
summary = "An ALTER that copies the whole table into a new file while holding a strong lock."
category = "Databases"
related = ["migration", "lock"]
posts = ["db-zero-downtime-migrations"]
+++

You can tell it happened by checking `pg_relation_filenode()` before and after: a new number means a new file. On a big table a rewrite blocks reads and writes for as long as the copy takes.
