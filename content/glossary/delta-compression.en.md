+++
title = "Delta compression"
summary = "Storing an object as a small difference against a similar base object."
category = "Git"
related = ["packfile"]
posts = ["git-workflows-packfiles"]
+++

Instead of storing a full copy, Git can store an object as instructions (a delta) on top of a similar base object. Deltas can chain: `git verify-pack -v` shows the chain depth. It is the main reason a packfile is much smaller than loose objects.
