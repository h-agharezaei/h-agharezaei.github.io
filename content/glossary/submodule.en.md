+++
title = "Submodule"
summary = "A repository nested inside another one and pinned to one exact commit."
category = "Git"
related = ["gitlink", "subtree"]
posts = ["git-submodule-subtree-worktree"]
+++

The parent repo does not copy the files; it stores a [gitlink](/glossary/gitlink/) to a commit in the other repo, plus the URL in `.gitmodules`. A plain clone leaves the directory empty until you run `git submodule update --init`.
