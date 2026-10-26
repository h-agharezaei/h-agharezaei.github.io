+++
title = "Remote-tracking branch"
summary = "ثبت محلی و فقط‌خواندنی از یک branch روی remote، مثل origin/main."
category = "Git"
fa_title = "remote-tracking branch"
related = ["git-ref", "git-branch"]
posts = ["git-branches-head-refs"]
+++

remote-tracking branchها زیر `.git/refs/remotes/<remote>/` هستند و فقط با `git fetch` یا `git push` به‌روز می‌شوند. آن‌ها وضعیت remote در آخرین ارتباط شما را نشان می‌دهند، نه وضعیت فعلی را.
