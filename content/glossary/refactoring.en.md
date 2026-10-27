+++
title = "Refactoring"
summary = "Changing the structure of code without changing its observable behavior."
category = "Engineering"
related = ["characterization-test", "regression"]
posts = ["eng-refactoring-safely", "eng-technical-debt"]
+++

Refactoring means rewriting the inside (names, functions, nesting) while every input still produces the same output. If behavior changes on purpose, that is a different change and belongs in a different commit. Without tests that pin the behavior you cannot know which one you did.
