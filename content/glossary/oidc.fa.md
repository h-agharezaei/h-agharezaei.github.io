+++
title = "OpenID Connect (OIDC)"
summary = "لایه‌ی هویتی نازک روی OAuth 2.0 که ID token و userinfo اضافه می‌کند تا کلاینت بداند چه کسی وارد شده."
category = "Security"
fa_title = "OIDC"
related = ["oauth2", "jwks", "jwt"]
posts = ["sec-oauth2-oidc"]
+++

OAuth2 تنها می‌گوید توکن چه کاری مجاز است؛ OIDC احراز هویت را اضافه می‌کند. کلاینت باید ID token را اعتبارسنجی کند: امضا، `iss`، `aud`، `exp` و `nonce`.
