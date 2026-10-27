+++
title = "Pagination"
summary = "Returning a large list in pages instead of all at once."
category = "Engineering"
related = ["keyset-pagination"]
posts = ["eng-api-design-versioning-pagination", "eng-openapi-contracts"]
+++

An API that lists many rows returns them a page at a time. The two common styles are offset (`page`/`per_page`) and keyset or cursor based, see [keyset pagination](/glossary/keyset-pagination/).
