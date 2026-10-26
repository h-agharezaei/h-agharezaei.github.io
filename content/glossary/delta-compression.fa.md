+++
title = "Delta compression"
summary = "ذخیره‌ی object به‌صورت تفاوت کوچک با یک object پایه."
category = "Git"
fa_title = "فشرده‌سازی delta"
related = ["packfile"]
posts = ["git-workflows-packfiles"]
+++

به‌جای ذخیره‌ی نسخه‌ی کامل، Git می‌تواند یک object را به‌صورت دستورهایی (delta) روی یک object پایه‌ی مشابه ذخیره کند. deltaها می‌توانند زنجیره بسازند و `git verify-pack -v` عمق زنجیره را نشان می‌دهد. دلیل اصلی کوچک‌تر بودن packfile نسبت به objectهای loose همین است.
