+++
title = "Dependency injection"
summary = "Passing dependencies (like time or a database) in from outside instead of creating them inside the function."
category = "Node.js"
related = ["test-double"]
posts = ["node-testing-builtin", "eng-testing-pyramid-tdd", "node-project-structure-config", "py-fastapi-pydantic"]
+++

Instead of calling `Date.now()` or opening a database connection itself, the function takes it as a parameter. A test passes a fake one and gets a deterministic result.
