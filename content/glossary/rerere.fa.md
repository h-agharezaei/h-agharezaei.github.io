+++
title = "rerere"
summary = "قابلیتی در Git (reuse recorded resolution) که حل قبلی یک conflict را دوباره اعمال می‌کند."
category = "Git"
fa_title = "استفاده‌ی دوباره از حل conflict"
related = ["merge-conflict"]
posts = ["git-resolve-conflicts"]
+++

با `rerere.enabled` فعال می‌شود. Git conflict و حل شما را در `.git/rr-cache` ذخیره می‌کند و دفعه‌ی بعد همان conflict را پر می‌کند. فایل را stage نمی‌کند.
