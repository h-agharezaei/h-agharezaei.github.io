+++
title = "Ref"
summary = "a human-readable name that points to a Git object."
category = "Git"
related = ["git-branch", "head", "remote-tracking-branch"]
posts = ["git-branches-head-refs"]
+++

A ref is a file under `.git/refs/` (branches, tags, remote-tracking branches) whose content is an object id. `git for-each-ref` lists them all and `git update-ref` writes them. A symbolic ref points to another ref instead of an id.
