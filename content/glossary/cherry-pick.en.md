+++
title = "cherry-pick"
summary = "Copies the patch of one commit onto the current branch as a new commit with a new hash."
category = "Git"
related = ["git-revert"]
posts = ["git-undo-reflog-revert"]
+++

`git cherry-pick -x <hash>` records the original hash in the message. The copy has the same patch-id as the original but a different hash. See also [git revert](/glossary/git-revert/).
