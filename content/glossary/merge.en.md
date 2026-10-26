+++
title = "merge"
summary = "joins two lines of history; if they diverged, Git creates a merge commit with two parents."
category = "Git"
related = ["merge-commit", "fast-forward", "rebase"]
posts = ["git-merge-vs-rebase"]
+++

A merge combines the work of another branch into the current one. If both sides have new commits, Git records a [merge commit](/glossary/merge-commit/) and keeps both histories as they happened.
