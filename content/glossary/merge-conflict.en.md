+++
title = "Merge conflict"
summary = "Git could not combine two changes to the same lines automatically and asks you to choose."
category = "Git"
related = ["rerere", "three-way-merge"]
posts = ["git-resolve-conflicts"]
+++

A conflict leaves `<<<<<<<`, `=======` and `>>>>>>>` markers in the file. You edit it, `git add` it and finish with `git commit` (or `--continue` in a rebase).
