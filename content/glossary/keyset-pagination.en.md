+++
title = "Keyset pagination"
summary = "Paging by 'rows after this key' instead of 'skip N rows'."
category = "Engineering"
related = ["pagination"]
posts = ["eng-api-design-versioning-pagination"]
+++

The client sends the sort key of the last row it saw (often wrapped in an opaque cursor) and the server returns the rows after it. Inserts and deletes before that point do not shift the next page, and with an index on the sort key it avoids scanning the skipped rows. See [pagination](/glossary/pagination/).
