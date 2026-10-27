+++
title = 'Parametrized test'
summary = 'one test body run over many input rows'
category = 'Python'
related = ["fixture"]
posts = ["py-testing-pytest"]
+++

A **parametrized test** runs the same test function once per row of inputs and expected values, and reports each row as its own test. In pytest this is `@pytest.mark.parametrize`. It is the Python counterpart of Go's table-driven tests.
