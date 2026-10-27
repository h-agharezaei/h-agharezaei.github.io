+++
title = "هوک Git"
summary = "اسکریپتی که Git در نقطه‌ای از جریان کار، مثلاً پیش از commit، خودش اجرا می‌کند."
category = "Git"
fa_title = "هوک Git"
related = []
posts = ["git-hooks-commit-hygiene", "sec-secrets-management"]
+++

هوک‌ها فایل‌های اجرایی‌اند که نامشان همان رویداد است (`pre-commit`، `commit-msg`، `pre-push`). اگر یکی از آن‌ها با کد غیرصفر خارج شود، Git عملیات را متوقف می‌کند. به‌صورت پیش‌فرض در `.git/hooks` هستند که version نمی‌شود، یا در پوشه‌ای که `core.hooksPath` مشخص می‌کند. گزینه‌ی `--no-verify` آن‌ها را رد می‌کند، پس مانع امنیتی نیستند و فقط حفاظ‌اند.
