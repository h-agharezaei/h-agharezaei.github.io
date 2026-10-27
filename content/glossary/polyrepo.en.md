+++
title = "Polyrepo"
summary = "Each service or library lives in its own repository and is released and versioned on its own."
category = "Engineering"
related = ["monorepo", "semver"]
posts = ["eng-monorepo-vs-polyrepo"]
+++

In a **polyrepo** layout every project has its own repository, history, CI and access rules. Shared code is consumed as a versioned dependency, so a cross-cutting change needs one pull request per repository. See also [monorepo](/glossary/monorepo/).
