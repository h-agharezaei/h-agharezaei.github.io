+++
title = "git reset"
summary = "branch فعلی را به commit دیگری می‌برد؛ mode تعیین می‌کند index و working tree چه شوند."
category = "Git"
fa_title = "ریست در Git"
related = ["staging-area", "reflog"]
posts = ["git-undo-reflog-revert"]
+++

`--soft` هم index و هم فایل‌ها را نگه می‌دارد، `--mixed` (پیش‌فرض) index را ریست می‌کند ولی فایل‌ها را نگه می‌دارد و `--hard` هر دو را ریست می‌کند، پس تغییرات commit‌نشده از بین می‌روند. برای پیدا کردن جای قبلی از [reflog](/fa/glossary/reflog/) استفاده کنید.
