+++
title = "Regression"
summary = "A bug that breaks something which used to work."
category = "Engineering"
related = ["git-bisect"]
posts = ["git-bisect", "eng-refactoring-safely", "sec-fuzzing"]
+++

A regression means there is a last good version and a first bad one, which is exactly what [git bisect](/glossary/git-bisect/) searches between. A test that fails now but passed before is the classic signal.
