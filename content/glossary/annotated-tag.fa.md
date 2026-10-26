+++
title = "Annotated tag"
summary = "tagی که خودش یک object با پیام، نویسنده و تاریخ است."
category = "Git"
fa_title = "annotated tag"
related = ["git-ref", "git-object"]
posts = ["git-branches-head-refs"]
+++

tag سبک فقط یک ref به یک commit است. annotated tag (`git tag -a`) یک object جداست که به commit اشاره می‌کند؛ برای همین `git cat-file -t` به‌جای `commit` عبارت `tag` را چاپ می‌کند.
