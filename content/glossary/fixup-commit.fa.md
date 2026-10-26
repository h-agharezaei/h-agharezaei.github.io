+++
title = "کامیت fixup"
summary = "کامیتی که قرار است هنگام rebase با autosquash داخل کامیت قبلی ادغام شود."
category = "Git"
fa_title = "کامیت fixup"
related = []
posts = ["git-hooks-commit-hygiene"]
+++

دستور `git commit --fixup <commit>` کامیتی با عنوان `fixup! <subject>` می‌سازد. بعد `git rebase -i --autosquash` آن را کنار هدفش می‌برد و ادغام می‌کند تا یک اصلاح کوچک در تاریخچه ردیف جداگانه نشود.
