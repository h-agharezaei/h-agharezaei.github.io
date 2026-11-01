+++
title = "ECDSA"
summary = "امضای دیجیتال روی منحنی بیضوی: یک hash را با کلید خصوصی امضا می‌کند و امضا جفت (r, s) است."
category = "Blockchain"
fa_title = "ECDSA"
related = ["secp256k1", "rfc-6979", "signature-malleability", "digital-signature", "nonce"]
posts = ["bc-keys-ecdsa-addresses"]
+++

بیت‌کوین و اتریوم تراکنش‌ها را با ECDSA روی [secp256k1](/fa/glossary/secp256k1/) امضا می‌کنند. هر امضا یک [nonce](/fa/glossary/nonce/) مخفی k لازم دارد و تکرار k با یک کلید، کلید خصوصی را لو می‌دهد.
