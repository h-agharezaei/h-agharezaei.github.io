+++
title = "reflog"
summary = "A local log of where HEAD and branch tips have pointed, used to recover commits after a reset or deleted branch."
category = "Git"
related = ["git-reset", "git-revert"]
posts = ["git-undo-reflog-revert", "git-branches-head-refs"]
+++

`git reflog` lists entries like `HEAD@{1}`. It is local to your clone, not pushed, and old entries expire (according to the docs, 90 days if reachable, 30 if not). It only knows about committed work. See [git reset](/glossary/git-reset/).
