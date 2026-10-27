+++
title = "Sparse checkout"
summary = "فقط بعضی پوشه‌ها را در working tree قرار می‌دهد."
category = "Git"
fa_title = "sparse checkout"
related = ["partial-clone"]
posts = ["git-workflows-packfiles", "eng-monorepo-vs-polyrepo"]
+++

`git sparse-checkout set app` باعث می‌شود working tree فقط `app/` را داشته باشد. همراه partial clone فقط blobهای لازم دانلود می‌شود. برای monorepoهای بزرگ مفید است.
