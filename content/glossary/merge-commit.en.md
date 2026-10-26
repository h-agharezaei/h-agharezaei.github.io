+++
title = "merge commit"
summary = "a commit with two parents that records the joining of two histories."
category = "Git"
related = ["merge", "fast-forward"]
posts = ["git-merge-vs-rebase", "git-undo-reflog-revert"]
+++

A merge commit is created by a non-fast-forward [merge](/glossary/merge/). It has two parents, so `git log --graph` shows the branch and join as a diamond.
