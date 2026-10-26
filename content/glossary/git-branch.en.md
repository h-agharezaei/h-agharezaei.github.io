+++
title = "Branch"
summary = "a movable pointer: a file holding one commit id."
category = "Git"
related = ["git-ref", "head", "fast-forward"]
posts = ["git-branches-head-refs"]
+++

A branch is just a file under `.git/refs/heads/` that contains the 40-character id of one [commit](/glossary/commit/). Making a commit on the current branch moves that file to the new commit. Creating a branch costs 41 bytes.
