+++
title = "secp256k1"
summary = "منحنی بیضوی y² = x³ + 7 روی یک میدان اول ۲۵۶ بیتی که بیت‌کوین و اتریوم برای کلید و امضا استفاده می‌کنند."
category = "Blockchain"
fa_title = "secp256k1"
related = ["ecdsa", "keccak-256"]
posts = ["bc-keys-ecdsa-addresses"]
+++

کلید خصوصی یک عدد ۲۵۶ بیتی d است و کلید عمومی نقطه‌ی d·G. پکیج استاندارد `crypto/ecdsa` در Go این منحنی را ندارد، پس از کتاب‌خانه‌ای مثل `github.com/decred/dcrd/dcrec/secp256k1/v4` استفاده می‌شود.
