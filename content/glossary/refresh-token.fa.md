+++
title = "Refresh token"
summary = "اعتبارنامه‌ای بلندمدت که کلاینت آن را با access token کوتاه‌مدت جدید عوض می‌کند."
category = "Security"
fa_title = "Refresh token"
related = ["oauth2", "bearer-token"]
posts = ["sec-oauth2-oidc"]
+++

با rotation هر استفاده یک refresh token تازه می‌دهد و قبلی را باطل می‌کند. اگر قبلی دوباره ظاهر شود، سرور می‌تواند آن را دزدی بداند و کل خانواده را باطل کند.
