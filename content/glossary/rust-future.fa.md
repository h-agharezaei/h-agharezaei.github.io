+++
title = "Future (Rust)"
fa_title = "Future در Rust"
summary = "مقداری که کاری نیمه‌تمام را نشان می‌دهد؛ async fn یکی از آن‌ها برمی‌گرداند و تا وقتی await یا poll نشود هیچ کاری نمی‌کند."
category = "Rust"
related = ["rust-async-await", "tokio"]
posts = ["rust-async-tokio"]
+++

صدا زدن یک `async fn` بدنه‌اش را اجرا نمی‌کند. یک `Future` برمی‌گرداند و بدنه فقط وقتی اجرا می‌شود که چیزی آن را poll کند، معمولاً با `.await` داخل یک تابع async دیگر یا با یک runtime مثل Tokio. futureای که هیچ‌وقت await نشود هرگز اجرا نمی‌شود؛ کامپایلر درباره‌اش هشدار می‌دهد.
