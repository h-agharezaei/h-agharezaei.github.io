+++
title = "Expression index"
summary = "An index built on the result of an expression such as lower(email) instead of a plain column."
category = "Databases"
related = ["sargable"]
posts = ["db-composite-partial-covering-indexes"]
+++

The query must use the same expression to benefit. It fixes [non-sargable](/glossary/sargable/) conditions without rewriting data.
