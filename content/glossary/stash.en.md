+++
title = "Stash"
summary = "a stack of shelved changes you can put back later."
category = "Git"
related = ["working-tree"]
posts = ["git-index-staging"]
+++

`git stash` saves modified tracked files and reverts the working tree to HEAD; `git stash pop` reapplies the newest entry and drops it. Untracked files are included only with `-u`.
