+++
title = "Branch"
summary = "اشاره‌گری قابل جابه‌جایی: فایلی که شناسه‌ی یک commit را نگه می‌دارد."
category = "Git"
fa_title = "شاخه (branch)"
related = ["git-ref", "head", "fast-forward"]
posts = ["git-branches-head-refs"]
+++

branch فقط یک فایل زیر `.git/refs/heads/` است که شناسه‌ی ۴۰ کاراکتری یک [commit](/fa/glossary/commit/) را نگه می‌دارد. با هر commit روی branch فعلی، این فایل به commit جدید اشاره می‌کند. ساختن یک branch فقط ۴۱ بایت هزینه دارد.
