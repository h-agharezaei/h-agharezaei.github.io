+++
title = "Merge conflict"
summary = "Git نتوانست دو تغییر روی یک خط‌ها را خودکار ترکیب کند و از شما می‌خواهد انتخاب کنید."
category = "Git"
fa_title = "تداخل merge"
related = ["rerere", "three-way-merge"]
posts = ["git-resolve-conflicts"]
+++

conflict خط‌های `<<<<<<<`، `=======` و `>>>>>>>` را در فایل می‌گذارد. آن را ویرایش می‌کنید، `git add` می‌زنید و با `git commit` (یا `--continue` در rebase) تمام می‌کنید.
