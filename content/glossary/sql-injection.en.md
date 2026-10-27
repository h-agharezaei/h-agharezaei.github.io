+++
title = "SQL injection"
summary = "An attack where user input becomes part of the SQL text and changes its meaning."
category = "Security"
related = ["sqlstate"]
posts = ["node-postgres-pg"]
+++

It happens when you build SQL by concatenating strings. The defense is parameterized queries (`$1`): the values travel separately from the SQL text, so they can never be read as SQL.
