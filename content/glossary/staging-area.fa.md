+++
title = "Staging area (index)"
fa_title = "Staging area (index)"
summary = "عکسی از چیزی که commit بعدی خواهد داشت، ذخیره‌شده در .git/index."
category = "Git"
related = ["working-tree", "head", "blob"]
posts = ["git-index-staging", "git-undo-reflog-revert"]
+++

index هر مسیر tracked را با mode فایل و شناسه‌ی blob آن فهرست می‌کند. `git add` آن را به‌روز می‌کند، `git commit` آن را به tree تبدیل می‌کند و `git restore --staged` ورودی‌ها را از آن بیرون می‌کشد.
