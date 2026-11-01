+++
title = "Account model"
summary = "دفتری که برای هر آدرس یک موجودی و یک nonce نگه می‌دارد، مثل اتریوم، به‌جای مجموعه‌ی خروجی‌های خرج‌نشده."
category = "Blockchain"
fa_title = "مدل حساب"
related = ["utxo", "nonce", "replay-attack"]
posts = ["bc-account-model-nonce", "bc-evm-internals-rust"]
+++

هر انتقال از فرستنده کم و به گیرنده اضافه می‌کند. چون یک انتقال امضاشده را می‌شود دوباره فرستاد، هر فرستنده یک nonce دارد که هر تراکنش باید با آن بخواند.
