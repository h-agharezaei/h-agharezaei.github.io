+++
title = "git bisect"
summary = "A Git command that binary-searches your history to find the first commit that introduced a bug."
category = "Git"
related = ["binary-search", "regression", "atomic-commit"]
posts = ["git-bisect"]
+++

`git bisect` takes one known-good and one known-bad commit and checks out the commit in the middle, asking you (or a script) whether it is good or bad. Each answer halves the range, so about log2(N) tests find the culprit. See [binary search](/glossary/binary-search/) and [regression](/glossary/regression/).
