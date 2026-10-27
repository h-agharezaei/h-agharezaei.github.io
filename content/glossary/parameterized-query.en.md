+++
title = "Parameterized query"
summary = "A SQL statement with placeholders (`$1`) whose values are sent separately from the SQL text."
category = "Security"
related = ["sql-injection"]
posts = ["sec-injection-xss"]
+++

The database parses the statement first and fills in values later, so a value can never change the structure of the query. Table and column names cannot be parameters.
