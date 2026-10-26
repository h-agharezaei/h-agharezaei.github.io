+++
title = "Atomic commit"
summary = "A commit that contains one complete, logical change and nothing else."
category = "Git"
related = ["git-bisect"]
posts = ["git-bisect"]
+++

Atomic commits keep each step small, buildable and easy to review or revert. They also make [git bisect](/glossary/git-bisect/) precise: the first bad commit it reports is a small diff, not a week of work.
