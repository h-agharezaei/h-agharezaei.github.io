+++
title = "Signature malleability"
summary = "یک امضای معتبر را بدون کلید خصوصی می‌شود به امضای معتبر دیگری برای همان پیام تبدیل کرد."
category = "Blockchain"
fa_title = "انعطاف‌پذیری امضا (malleability)"
related = ["ecdsa"]
posts = ["bc-keys-ecdsa-addresses"]
+++

در [ECDSA](/fa/glossary/ecdsa/) هر دو (r, s) و (r, n − s) معتبرند. طبق مستندات، تراکنش اتریوم (EIP-2) مقدار S بزرگ را رد می‌کند و policy رله‌ی Bitcoin Core هم همین‌طور، تا هر امضا یک شکل داشته باشد.
