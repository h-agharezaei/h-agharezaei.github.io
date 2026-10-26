+++
title = "Remote-tracking branch"
summary = "a local, read-only record of a branch on a remote, like origin/main."
category = "Git"
related = ["git-ref", "git-branch"]
posts = ["git-branches-head-refs"]
+++

Remote-tracking branches live under `.git/refs/remotes/<remote>/` and are updated only by `git fetch` or `git push`. They show what the remote looked like the last time you talked to it, not what it looks like now.
