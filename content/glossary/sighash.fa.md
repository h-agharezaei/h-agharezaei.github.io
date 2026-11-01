+++
title = "Sighash"
summary = "hash یک تراکنش که امضا واقعاً روی آن است؛ خود امضاها در آن نیستند."
category = "Blockchain"
fa_title = "sighash"
related = ["digital-signature", "signature-malleability", "canonical-encoding"]
posts = ["bc-transactions-utxo"]
+++

امضا نمی‌تواند خودش را امضا کند، پس بایت‌های امضاشده همان تراکنش با فیلد امضای خالی است. هر چیزی که sighash پوشش ندهد را هر کسی می‌تواند بدون شکستن امضا عوض کند.
