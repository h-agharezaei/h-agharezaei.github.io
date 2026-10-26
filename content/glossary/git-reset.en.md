+++
title = "git reset"
summary = "Moves the current branch to another commit; the mode decides what happens to the index and working tree."
category = "Git"
related = ["staging-area", "reflog"]
posts = ["git-undo-reflog-revert"]
+++

`--soft` keeps the index and files, `--mixed` (default) resets the index but keeps files, `--hard` resets both, so uncommitted edits are lost. Use [reflog](/glossary/reflog/) to find the old position.
