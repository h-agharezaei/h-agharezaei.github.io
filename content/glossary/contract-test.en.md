+++
title = "Contract test"
summary = "A test that checks real requests or responses against the API contract, not against hand-written expectations."
category = "Engineering"
related = ["api-contract", "openapi"]
posts = ["eng-openapi-contracts"]
+++

The test calls the handler and validates the response with the schema from the spec. When code and spec drift apart, the test fails.
