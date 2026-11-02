+++
title = "P2PKH"
summary = "پرداخت به hash کلید عمومی: قفلی در بیت‌کوین که کلید عمومی منطبق با یک HASH160 ذخیره‌شده و امضای معتبر همان کلید را می‌خواهد."
category = "Blockchain"
fa_title = "P2PKH"
related = ["bitcoin-script", "ecdsa", "digital-signature"]
posts = ["bc-bitcoin-script-rust"]
+++

اسکریپت قفل `OP_DUP OP_HASH160 <pubkey hash> OP_EQUALVERIFY OP_CHECKSIG` است و خرج‌کننده `<sig> <pubkey>` را می‌دهد. HASH160 یعنی RIPEMD-160 روی SHA-256. ببینید [Bitcoin Script](/fa/glossary/bitcoin-script/).
