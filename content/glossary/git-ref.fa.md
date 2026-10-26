+++
title = "Ref"
summary = "نامی خوانا که به یک object گیت اشاره می‌کند."
category = "Git"
fa_title = "ref"
related = ["git-branch", "head", "remote-tracking-branch"]
posts = ["git-branches-head-refs"]
+++

ref فایلی زیر `.git/refs/` است (branch، tag، remote-tracking branch) که محتوایش شناسه‌ی یک object است. `git for-each-ref` همه را فهرست می‌کند و `git update-ref` آن‌ها را می‌نویسد. symbolic ref به‌جای شناسه، به ref دیگری اشاره می‌کند.
