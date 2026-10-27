+++
title = "Stemming"
summary = "Reducing a word to its stem so that different forms match, for example running, runs and run all become run."
category = "Databases"
related = ["tsvector"]
posts = ["db-jsonb-fulltext-search"]
+++

PostgreSQL does this with a dictionary that belongs to a text search configuration such as `english`. The `simple` configuration does no stemming. Stemming is language specific, and irregular forms such as `ran` may not be reduced.
