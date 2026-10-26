+++
title = "Normalization"
summary = "Split tables so each fact is stored exactly once."
category = "Databases"
related = ["primary-key", "foreign-key", "denormalization"]
posts = ["db-schema-design-normalization"]
+++

Normalization is the process of splitting a table into smaller ones so that every fact (a customer's email, a product's price) lives in exactly one place. It removes update, insert and delete anomalies. The usual steps are called 1NF, 2NF and 3NF. See [denormalization](/glossary/denormalization/) for the opposite trade.
