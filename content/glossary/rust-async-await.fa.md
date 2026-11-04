+++
title = "async/await (Rust)"
fa_title = "async/await در Rust"
summary = "نحوی برای نوشتن کدی که بدون بستن یک thread منتظر می‌ماند: async fn یک future می‌سازد و .await تا آماده‌شدنش مکث می‌کند."
category = "Rust"
related = ["rust-future", "tokio"]
posts = ["rust-async-tokio"]
+++

داخل یک `async fn`، `.await` نقطه‌ای است که task می‌تواند مکث کند تا thread کار دیگری را اجرا کند. کد بین دو `.await` بدون وقفه اجرا می‌شود. Rust اجراکننده‌ی داخلی ندارد، پس کد async برای اجرا به یک crate از نوع runtime نیاز دارد.
