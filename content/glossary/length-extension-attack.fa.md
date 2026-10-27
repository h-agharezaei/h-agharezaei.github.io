+++
title = "Length extension attack"
summary = "حمله‌ای به هش‌هایی مثل SHA-256 که با دانستن H(secret||msg) می‌توان بدون راز، H(secret||msg||extra) را ساخت."
category = "Security"
fa_title = "حمله‌ی length extension"
related = ["hmac"]
posts = ["sec-crypto-mistakes"]
+++

از نحوه‌ی نگه‌داشتن حالت داخلی در هش‌های Merkle-Damgard می‌آید. HMAC راه‌حل استاندارد است.
