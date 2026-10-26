+++
title = "rebase"
summary = "replays your commits on top of another base, producing new commits with new hashes."
category = "Git"
related = ["merge", "force-push", "fast-forward"]
posts = ["git-merge-vs-rebase", "git-resolve-conflicts"]
+++

Rebase takes the commits of your branch and re-applies them one by one on top of another commit. The result is a straight line of history, but every replayed commit is a new object, so its hash changes. That is why rebasing commits others already have is dangerous.
