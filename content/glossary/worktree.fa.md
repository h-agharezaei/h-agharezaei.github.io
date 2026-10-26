+++
title = "Worktree"
fa_title = "ورک‌تری"
summary = "یک پوشه‌ی کاری اضافه متصل به همان repository که branch خودش را checkout کرده است."
category = "Git"
related = ["working-tree", "head"]
posts = ["git-submodule-subtree-worktree"]
+++

با `git worktree add ../fix -b fix` می‌توانید دو branch را همزمان checkout کنید، بدون clone دوباره. گیت اجازه نمی‌دهد یک branch در دو worktree باز باشد.
