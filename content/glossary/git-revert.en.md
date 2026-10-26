+++
title = "git revert"
summary = "Undoes a commit by adding a new commit with the opposite patch, leaving history intact."
category = "Git"
related = ["cherry-pick", "reflog"]
posts = ["git-undo-reflog-revert"]
+++

Safe on shared branches because it never rewrites history. Reverting a merge commit needs `-m 1` to choose the mainline parent. Compare with [reflog](/glossary/reflog/) and `reset`.
