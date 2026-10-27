+++
title = 'Fixture'
summary = 'a function that prepares (and cleans up) what a test needs'
category = 'Python'
related = ["test-double", "context-manager"]
posts = ["py-testing-pytest"]
+++

A **fixture** in pytest is a function marked with `@pytest.fixture`. A test asks for it by naming it as a parameter, and pytest runs it first and passes in the result. With `yield`, the code after the `yield` runs as teardown. Its scope (function, module, session) controls how often it is rebuilt.
