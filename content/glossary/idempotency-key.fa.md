+++
title = "Idempotency key"
summary = "شناسه‌ی یکتایی که کلاینت همراه درخواست می‌فرستد تا سرور تکرار را تشخیص بدهد و به‌جای اجرای دوباره، نتیجه‌ی اول را برگرداند."
category = "Distributed"
fa_title = "کلید idempotency"
related = ["idempotency","at-least-once-delivery"]
posts = ["ds-capstone"]
+++

سرور کلید را همراه نتیجه‌ی اجرای اول نگه می‌دارد. درخواستی که دوباره با همان کلید برسد (retry بعد از timeout، دوبار کلیک) همان جواب ذخیره‌شده را می‌گیرد و چیزی تغییر نمی‌کند. ببینید [idempotency](/fa/glossary/idempotency/).
