+++
title = "Submodule"
fa_title = "زیرماژول"
summary = "یک repository تو در تو که به یک commit مشخص پین شده است."
category = "Git"
related = ["gitlink", "subtree"]
posts = ["git-submodule-subtree-worktree"]
+++

repository والد فایل‌ها را کپی نمی‌کند؛ یک [gitlink](/fa/glossary/gitlink/) به یک commit در repository دیگر و نشانی آن را در `.gitmodules` نگه می‌دارد. clone ساده پوشه را خالی می‌گذارد تا `git submodule update --init` را بزنید.
