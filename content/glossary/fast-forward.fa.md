+++
title = "fast-forward"
fa_title = "fast-forward"
summary = "جلو بردن اشاره‌گر branch روی یک خط مستقیم از commitها، بدون ساختن commit جدید."
category = "Git"
related = ["merge", "rebase", "head"]
posts = ["git-merge-vs-rebase", "git-branches-head-refs"]
+++

اگر branch مقصد از زمان جدا شدن commit تازه‌ای نداشته باشد، گیت فقط اشاره‌گر آن را جلو می‌برد و چیز جدیدی نمی‌سازد. `--ff-only` هر حالت دیگر را رد می‌کند و `--no-ff` حتی وقتی fast-forward ممکن است یک merge commit می‌سازد.
