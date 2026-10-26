+++
title = ".gitignore"
summary = "a file of patterns telling Git which untracked files to leave alone."
category = "Git"
related = ["staging-area"]
posts = ["git-index-staging"]
+++

Ignoring only affects untracked files. A file that is already tracked stays tracked until you run `git rm --cached`. `git check-ignore -v` shows which rule matches.
