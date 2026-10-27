+++
title = "Schema validation"
summary = "Checking untrusted data against a declared shape (types, ranges, required fields) at the boundary, before the rest of the code uses it."
category = "Node.js"
related = ["json-schema", "trust-boundary", "mass-assignment"]
posts = ["node-validation-zod"]
+++

A schema describes what valid input looks like; parsing either returns clean data or a list of issues. Libraries such as Zod do this in code instead of a separate schema file.
