+++
title = "ecrecover"
summary = "precompile ای در EVM که آدرس صاحب یک امضای ECDSA روی یک hash سی‌ودو بایتی را برمی‌گرداند."
category = "Blockchain"
fa_title = "ecrecover"
related = ["ecdsa", "digital-signature", "signature-malleability"]
posts = ["bc-bridges-cross-chain"]
+++

برای امضای نامعتبر به‌جای خطا آدرس صفر برمی‌گرداند، پس فراخوان باید آن را چک کند. قراردادها معمولاً نسخه‌ی با `s` بالای امضا را هم رد می‌کنند ([signature malleability](/fa/glossary/signature-malleability/)).
