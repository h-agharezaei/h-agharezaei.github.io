+++
title = "BIP-44"
summary = "قراردادی برای مسیرهای BIP-32 به شکل m / purpose' / coin_type' / account' / change / address_index."
category = "Blockchain"
fa_title = "BIP-44"
related = ["bip-32", "hd-wallet"]
posts = ["bc-hd-wallets-rust"]
+++

purpose برابر ۴۴ است و coin_type از فهرست SLIP-44 می‌آید (۶۰ برای Ether، صفر برای بیت‌کوین). سه سطح اول hardened هستند. برای اتریوم آدرس‌های معمول m/44'/60'/0'/0/i هستند.
