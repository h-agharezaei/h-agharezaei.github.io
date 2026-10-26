+++
title = "Git object"
summary = "A blob, tree, commit or tag stored under its hash in .git/objects."
category = "Git"
related = ["blob", "git-tree", "commit", "sha-1"]
posts = ["git-how-git-thinks", "git-branches-head-refs"]
+++

Everything Git stores is an object, named by the hash of its content and kept zlib-compressed as a loose file. Objects are never modified, only added.
