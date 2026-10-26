+++
title = "squash merge"
summary = "collapses all commits of a branch into one new commit on the target branch."
category = "Git"
related = ["merge", "rebase"]
posts = ["git-merge-vs-rebase"]
+++

`git merge --squash` applies the combined changes of a branch to your working tree and stops. You commit once yourself. The result has no link back to the original commits, so Git will still list the branch as not merged.
