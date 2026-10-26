+++
title = "Gitlink"
summary = "A tree entry (mode 160000) that records a commit id from another repository."
category = "Git"
related = ["submodule", "git-tree"]
posts = ["git-submodule-subtree-worktree"]
+++

`git ls-tree HEAD` shows it as `160000 commit <sha> <path>`. This is how a [submodule](/glossary/submodule/) is stored inside the parent repo.
