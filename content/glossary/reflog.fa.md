+++
title = "reflog"
summary = "گزارش محلی از جاهایی که HEAD و سر branchها به آن اشاره کرده‌اند؛ برای بازیابی commit بعد از reset یا حذف branch."
category = "Git"
fa_title = "reflog"
related = ["git-reset", "git-revert"]
posts = ["git-undo-reflog-revert", "git-branches-head-refs"]
+++

`git reflog` ورودی‌هایی مثل `HEAD@{1}` را نشان می‌دهد. فقط روی همین clone است، push نمی‌شود و ورودی‌های قدیمی منقضی می‌شوند (طبق مستندات ۹۰ روز اگر reachable باشند و ۳۰ روز اگر نباشند). فقط کار commit‌شده را به یاد دارد. ببینید [git reset](/fa/glossary/git-reset/).
