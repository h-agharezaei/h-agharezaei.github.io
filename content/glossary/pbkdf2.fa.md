+++
title = "PBKDF2"
summary = "یک key derivation function که HMAC را روی رمز و salt بارها تکرار می‌کند تا حدس زدن کند شود."
category = "Blockchain"
fa_title = "PBKDF2"
related = ["key-derivation-function", "hmac", "salt", "bip-39"]
posts = ["bc-hd-wallets-rust"]
+++

قدیمی‌تر و ساده‌تر از scrypt یا Argon2 است و حافظه‌ی زیادی لازم ندارد. [BIP-39](/fa/glossary/bip-39/) آن را با HMAC-SHA512 و ۲۰۴۸ دور به کار می‌برد تا از mnemonic یک seed بسازد.
