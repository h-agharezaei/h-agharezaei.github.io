+++
title = "fast-forward"
summary = "moving a branch pointer ahead along a straight line of commits, with no new commit."
category = "Git"
related = ["merge", "rebase", "head"]
posts = ["git-merge-vs-rebase", "git-branches-head-refs"]
+++

If the branch you merge into has no commits of its own since the split, Git just moves its pointer forward. Nothing new is created. `--ff-only` makes Git refuse anything else, and `--no-ff` forces a merge commit even when a fast-forward is possible.
