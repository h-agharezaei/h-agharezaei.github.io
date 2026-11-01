+++
title = "Keccak-256"
summary = "hash اصلی Keccak که اتریوم استفاده می‌کند؛ padding آن با SHA3-256 استاندارد فرق دارد و خروجی‌ها یکی نیستند."
category = "Blockchain"
fa_title = "Keccak-256"
related = ["eip-55", "secp256k1"]
posts = ["bc-keys-ecdsa-addresses"]
+++

Keccak-256 ورودی خالی با `c5d24601` شروع می‌شود. در Go از `sha3.NewLegacyKeccak256` در `golang.org/x/crypto/sha3` استفاده کنید، نه `sha3.New256`.
