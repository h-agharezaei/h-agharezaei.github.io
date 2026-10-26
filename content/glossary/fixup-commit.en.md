+++
title = "Fixup commit"
summary = "A commit marked to be folded into an earlier commit during an autosquash rebase."
category = "Git"
related = []
posts = ["git-hooks-commit-hygiene"]
+++

`git commit --fixup <commit>` creates a commit titled `fixup! <subject>`. Later `git rebase -i --autosquash` moves it next to its target and squashes it, so a small correction never becomes its own entry in history.
