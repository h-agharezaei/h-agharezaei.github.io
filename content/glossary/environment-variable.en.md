+++
title = "Environment variable"
summary = "A named string a process inherits from its parent, used to pass configuration such as ports and keys."
category = "Node.js"
related = ["composition-root"]
posts = ["node-project-structure-config", "sec-secrets-management"]
+++

A named string a process inherits from its parent, used to pass configuration such as ports and keys. In Node.js they appear in `process.env`. Every value is a string, so numbers and booleans must be parsed and validated.
