+++
title = "Worktree"
summary = "An extra working directory attached to the same repository, with its own checked-out branch."
category = "Git"
related = ["working-tree", "head"]
posts = ["git-submodule-subtree-worktree"]
+++

`git worktree add ../fix -b fix` lets you have two branches checked out at once without cloning again. Git refuses to check out the same branch in two worktrees.
