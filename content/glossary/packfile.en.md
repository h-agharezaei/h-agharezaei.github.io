+++
title = "Packfile"
summary = "A single Git file that stores many objects compactly, usually with delta compression."
category = "Git"
related = ["delta-compression", "shallow-clone"]
posts = ["git-workflows-packfiles"]
+++

A packfile (`.git/objects/pack/*.pack`) stores many Git objects in one file, with an `.idx` index for lookup. `git gc` and `git repack` create them, and fetch and push transfer them. See [delta compression](/glossary/delta-compression/).
