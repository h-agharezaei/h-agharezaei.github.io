+++
title = "Access control"
summary = "قاعده‌هایی که تعیین می‌کنند چه کسی کدام تابع را صدا بزند؛ در قرارداد معمولاً یک چک صریح روی msg.sender مثل onlyOwner."
category = "Blockchain"
fa_title = "کنترل دسترسی (access control)"
related = ["authorization", "least-privilege", "tx-origin"]
posts = ["bc-contract-security"]
+++

باگ‌های رایج: نبودن چک روی تابع ویژه، و `initialize()` که هر کسی، یا دوباره، صدایش می‌زند. هر تابع ویژه تستی می‌خواهد که نشان دهد غریبه رد می‌شود.
