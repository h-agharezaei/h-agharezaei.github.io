+++
title = "Pydantic"
summary = "A Python library that validates and converts data using type hints."
category = "Python"
related = ["type-hint", "schema-validation"]
posts = ["py-fastapi-pydantic"]
+++

Pydantic builds models from classes with type annotations. `Model.model_validate(data)` checks and converts the data (lax mode turns `"5"` into 5) and raises `ValidationError` with a list of errors. FastAPI uses it for request and response bodies.
