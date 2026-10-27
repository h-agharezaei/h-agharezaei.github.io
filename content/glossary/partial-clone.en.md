+++
title = "Partial clone"
summary = "A clone that skips some objects (e.g. file contents) and fetches them on demand."
category = "Git"
related = ["sparse-checkout", "shallow-clone"]
posts = ["git-workflows-packfiles", "eng-monorepo-vs-polyrepo"]
+++

With `--filter=blob:none` Git keeps the full commit history but downloads file contents only when needed, from a promisor remote that allows filters. Offline, a missing blob is an error. Often combined with [sparse checkout](/glossary/sparse-checkout/).
