+++
title = "Surrogate key"
summary = "An artificial row identifier with no business meaning, such as an identity number."
category = "Databases"
related = ["primary-key"]
posts = ["db-schema-design-normalization"]
+++

A surrogate key is an identifier invented by the database, for example a `GENERATED ALWAYS AS IDENTITY` integer. It never changes, unlike a natural key such as an email. Keep a UNIQUE constraint on the natural key anyway. See [primary key](/glossary/primary-key/).
