+++
title = "Cancellation by drop"
fa_title = "لغو با drop"
summary = "در Rust ناهم‌گام یک future را با drop کردنش لغو می‌کنید؛ در همان .await فعلی می‌ایستد و مقدارهای محلی‌اش نابود می‌شوند."
category = "Rust"
related = ["rust-future", "tokio"]
posts = ["rust-async-tokio"]
+++

`select!` و `timeout` futureهایی را که می‌بازند با drop کردن لغو می‌کنند. کدی که بعد از `.await` منتظر آمده هرگز اجرا نمی‌شود، پس پاک‌سازی باید در پیاده‌سازی `Drop` باشد، نه در دستورهای بعد از await.
