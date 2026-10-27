+++
title = "PKCE"
summary = "Proof Key for Code Exchange: کلاینت در درخواست توکن ثابت می‌کند همان است که درخواست مجوز را شروع کرده."
category = "Security"
fa_title = "PKCE"
related = ["oauth2", "authorization-code-flow"]
posts = ["sec-oauth2-oidc"]
+++

کلاینت یک verifier تصادفی می‌سازد، هش SHA-256 آن (challenge) را در درخواست مجوز و خود verifier را در درخواست توکن می‌فرستد. code دزدیده‌شده بدون verifier به‌درد نمی‌خورد.
