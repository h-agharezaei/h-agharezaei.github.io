+++
title = "rerere"
summary = "Git feature (reuse recorded resolution) that replays a conflict resolution you made before."
category = "Git"
related = ["merge-conflict"]
posts = ["git-resolve-conflicts"]
+++

Enable with `rerere.enabled`. Git stores the conflict and your fix in `.git/rr-cache` and fills the file next time the same conflict appears. It does not stage the file.
