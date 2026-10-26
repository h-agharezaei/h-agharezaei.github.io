+++
title = "Hunk"
summary = "one contiguous block of changes inside a diff."
category = "Git"
related = ["staging-area"]
posts = ["git-index-staging"]
+++

A diff of one file may contain several hunks, each starting with an `@@` line. `git add -p` lets you stage them one by one.
