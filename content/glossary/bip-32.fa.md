+++
title = "BIP-32"
summary = "استاندارد ساختن درختی از کلیدهای فرزند از یک کلید master و یک chain code با HMAC-SHA512."
category = "Blockchain"
fa_title = "BIP-32"
related = ["hd-wallet", "xpub", "hardened-derivation", "bip-44"]
posts = ["bc-hd-wallets-rust"]
+++

کلید master و chain code سی‌ودو بایتی دو نیمه‌ی HMAC-SHA512("Bitcoin seed", seed) هستند. هر فرزند از HMAC-SHA512(chain code, داده‌ی کلید والد || شماره) ساخته می‌شود: نیمه‌ی چپ کلید والد را جابه‌جا می‌کند و نیمه‌ی راست chain code فرزند می‌شود.
