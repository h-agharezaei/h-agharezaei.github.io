+++
title = "Test pyramid"
summary = "A model: many fast unit tests, fewer integration tests, very few end-to-end tests."
category = "Engineering"
related = ["tdd", "flaky-test"]
posts = ["eng-testing-pyramid-tdd"]
+++

A way to think about the cost of tests. Tests near the bottom (unit) are cheap, fast and stable; tests near the top (end-to-end) are slow, costly and more likely to be flaky. It is a trade-off model, not a rule.
