+++
title = "Packfile"
summary = "فایل فشرده‌ی گیت که چند object را با هم نگه می‌دارد."
category = "Git"
fa_title = "Packfile"
related = ["delta-compression", "shallow-clone"]
posts = ["git-workflows-packfiles"]
+++

packfile (`.git/objects/pack/*.pack`) چند object گیت را در یک فایل نگه می‌دارد و یک فایل `.idx` برای جست‌وجو دارد. `git gc` و `git repack` آن را می‌سازند و fetch و push آن را منتقل می‌کنند. [delta compression](/fa/glossary/delta-compression/) را ببینید.
