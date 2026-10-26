+++
title = "force push"
summary = "overwrites a remote branch with your local one, even if that discards commits; prefer --force-with-lease."
category = "Git"
related = ["rebase", "merge"]
posts = ["git-merge-vs-rebase"]
+++

`git push --force` makes the remote branch point where yours does. After a [rebase](/glossary/rebase/) it is needed, but it can throw away teammates' commits. `--force-with-lease` refuses if the remote moved since you last fetched.
