+++
title = "Conventional Commits"
summary = "قرارداد نوشتن subject کامیت به شکل type(scope): summary."
category = "Git"
fa_title = "Conventional Commits"
related = ["git-hook"]
posts = ["git-hooks-commit-hygiene"]
+++

نوع‌هایی مثل `feat`، `fix`، `docs` و `chore` تاریخچه را قابل‌پیمایش می‌کنند و ابزارها می‌توانند از آن changelog بسازند. مثال: `fix(api): handle empty body`. این فقط یک قرارداد است و تنها وقتی اعمال می‌شود که hook از نوع `commit-msg` یا یک بررسی در CI اضافه کنید.
