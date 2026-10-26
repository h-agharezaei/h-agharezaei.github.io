+++
title = "Staging area (index)"
summary = "the snapshot of what the next commit will contain, stored in .git/index."
category = "Git"
related = ["working-tree", "head", "blob"]
posts = ["git-index-staging", "git-undo-reflog-revert"]
+++

The index lists every tracked path with its file mode and the id of its blob. `git add` updates it, `git commit` turns it into a tree, and `git restore --staged` pulls entries back out.
