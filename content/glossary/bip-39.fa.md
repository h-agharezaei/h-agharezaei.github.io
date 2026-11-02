+++
title = "BIP-39"
summary = "استانداردی که entropy تصادفی را به فهرستی از کلمه‌ها (mnemonic) و کلمه‌ها را به یک seed شصت‌وچهار بایتی تبدیل می‌کند."
category = "Blockchain"
fa_title = "BIP-39"
related = ["hd-wallet", "pbkdf2", "bip-32"]
posts = ["bc-hd-wallets-rust"]
+++

۱۲۸ تا ۲۵۶ بیت entropy به‌همراه یک checksum از SHA-256 به تکه‌های ۱۱ بیتی تقسیم می‌شود و هر تکه یک کلمه از فهرست ۲۰۴۸تایی است. seed حاصل [PBKDF2](/fa/glossary/pbkdf2/)-HMAC-SHA512 روی کلمه‌ها با salt برابر "mnemonic" + passphrase و ۲۰۴۸ دور است.
