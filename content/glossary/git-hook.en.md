+++
title = "Git hook"
summary = "A script Git runs automatically at a point in its workflow, such as before a commit."
category = "Git"
related = []
posts = ["git-hooks-commit-hygiene", "sec-secrets-management"]
+++

Hooks are executable files named after the event (`pre-commit`, `commit-msg`, `pre-push`). If one exits non-zero, Git aborts the operation. They live in `.git/hooks` by default, which is not versioned, or in the directory set by `core.hooksPath`. `--no-verify` skips them, so they are a guard rail, not security.
