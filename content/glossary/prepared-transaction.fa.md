+++
title = "Prepared transaction"
summary = "در PostgreSQL تراکنشی که با PREPARE TRANSACTION از session جدا و روی دیسک ذخیره می‌شود و بعداً با COMMIT PREPARED یا ROLLBACK PREPARED تمام می‌شود."
category = "Distributed"
fa_title = "تراکنش prepared"
related = ["two-phase-commit", "lock"]
posts = ["ds-saga-vs-2pc"]
+++

از restart جان سالم به در می‌برد و تا وقتی کسی تمامش نکند lockهایش را نگه می‌دارد. این بلوک سازنده‌ی two-phase commit با یک transaction manager بیرونی است.
