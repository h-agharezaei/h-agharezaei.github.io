+++
title = "Annotated tag"
summary = "a tag stored as its own object with a message, author and date."
category = "Git"
related = ["git-ref", "git-object"]
posts = ["git-branches-head-refs"]
+++

A lightweight tag is only a ref pointing at a commit. An annotated tag (`git tag -a`) is a separate tag object that points at the commit, so `git cat-file -t` prints `tag` for it instead of `commit`.
