+++
title = "squash merge"
fa_title = "squash merge"
summary = "همه‌ی commitهای یک branch را به یک commit جدید روی branch مقصد تبدیل می‌کند."
category = "Git"
related = ["merge", "rebase"]
posts = ["git-merge-vs-rebase"]
+++

`git merge --squash` مجموع تغییرات یک branch را روی درخت کاری اعمال می‌کند و می‌ایستد؛ شما یک بار commit می‌کنید. نتیجه پیوندی به commitهای اصلی ندارد، برای همین گیت هنوز آن branch را merge نشده می‌داند.
