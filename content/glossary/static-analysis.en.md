+++
title = "Static analysis"
summary = "Checking source code for likely bugs without running it."
category = "Engineering"
related = ["code-review", "ci"]
posts = ["eng-code-review"]
+++

Tools such as `go vet` and staticcheck read the code and report suspicious patterns, for example a wrong format verb. They are fast and tireless, but they only know the patterns they were written for.
