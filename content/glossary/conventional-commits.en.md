+++
title = "Conventional Commits"
summary = "A convention for commit subjects shaped like type(scope): summary."
category = "Git"
related = ["git-hook"]
posts = ["git-hooks-commit-hygiene"]
+++

Types such as `feat`, `fix`, `docs` and `chore` make history easy to scan and let tools build changelogs. Example: `fix(api): handle empty body`. It is a convention, enforced only if you add a `commit-msg` hook or a CI check.
