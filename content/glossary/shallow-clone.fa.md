+++
title = "Shallow clone"
summary = "clone با تاریخچه‌ی کوتاه‌شده، مثل --depth 1."
category = "Git"
fa_title = "clone کم‌عمق"
related = ["partial-clone"]
posts = ["git-workflows-packfiles"]
+++

`git clone --depth 1` فقط آخرین commit را می‌گیرد. سریع و کوچک است ولی دستورهای تاریخچه چیز کمی می‌بینند. `git fetch --unshallow` بقیه را برمی‌گرداند. [partial clone](/fa/glossary/partial-clone/) را هم ببینید.
