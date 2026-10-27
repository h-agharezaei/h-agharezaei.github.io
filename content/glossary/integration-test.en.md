+++
title = "Integration test"
summary = "A test that runs several parts together, such as a service with a repository."
category = "Engineering"
related = ["test-pyramid", "test-double"]
posts = ["eng-testing-pyramid-tdd"]
+++

It checks that the parts fit together. It is slower and less precise than a unit test when it fails, but catches wiring mistakes that unit tests cannot. It may use a fake instead of a real database.
