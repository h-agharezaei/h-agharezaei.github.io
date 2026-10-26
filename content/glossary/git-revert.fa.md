+++
title = "git revert"
summary = "یک commit را با افزودن commit جدیدی با patch معکوس برمی‌گرداند و تاریخچه را دست نمی‌زند."
category = "Git"
fa_title = "revert در Git"
related = ["cherry-pick", "reflog"]
posts = ["git-undo-reflog-revert"]
+++

روی branchهای مشترک امن است چون تاریخچه را بازنویسی نمی‌کند. revert کردن merge commit به `-m 1` برای انتخاب parent اصلی نیاز دارد. با [reflog](/fa/glossary/reflog/) و `reset` مقایسه کنید.
