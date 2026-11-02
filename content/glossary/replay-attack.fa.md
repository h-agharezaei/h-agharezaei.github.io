+++
title = "Replay attack"
summary = "فرستادن دوباره‌ی یک پیام امضاشده‌ی معتبر تا دو بار اثر کند، یا روی سیستمی که برایش نبوده."
category = "Blockchain"
fa_title = "حمله‌ی replay"
related = ["nonce", "chain-id", "account-model"]
posts = ["bc-account-model-nonce", "bc-bridges-cross-chain"]
+++

امضا معتبر می‌ماند، پس گیرنده برای تشخیص پیام تکراری state لازم دارد: یک nonce یا شماره‌ی ترتیب، زمان انقضا، یا زمینه‌ای مثل chain ID داخل داده‌ی امضاشده.
