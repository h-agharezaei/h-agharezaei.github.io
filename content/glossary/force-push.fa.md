+++
title = "force push"
fa_title = "force push"
summary = "branch ریموت را با نسخه‌ی محلی بازنویسی می‌کند، حتی اگر commitهایی حذف شوند؛ --force-with-lease ترجیح دارد."
category = "Git"
related = ["rebase", "merge"]
posts = ["git-merge-vs-rebase"]
+++

`git push --force` اشاره‌گر branch ریموت را به جای branch شما می‌برد. بعد از [rebase](/fa/glossary/rebase/) لازم می‌شود، اما می‌تواند commitهای هم‌تیمی‌ها را دور بریزد. `--force-with-lease` اگر ریموت از آخرین fetch شما تغییر کرده باشد رد می‌کند.
