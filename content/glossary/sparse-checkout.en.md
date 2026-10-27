+++
title = "Sparse checkout"
summary = "Checking out only chosen directories into the working tree."
category = "Git"
related = ["partial-clone"]
posts = ["git-workflows-packfiles", "eng-monorepo-vs-polyrepo"]
+++

`git sparse-checkout set app` makes the working tree contain only `app/`. Combined with a partial clone, only the needed blobs are downloaded. Useful for large monorepos.
