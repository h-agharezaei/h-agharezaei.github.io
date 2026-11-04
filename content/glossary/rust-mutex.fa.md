+++
title = "Mutex (Rust)"
fa_title = "Mutex در Rust"
summary = "قفلی که صاحب داده‌ی محافظت‌شده است؛ lock() یک guard برمی‌گرداند که با خروج از scope قفل را باز می‌کند."
category = "Rust"
related = ["arc", "data-race", "interior-mutability"]
posts = ["rust-concurrency-threads"]
+++

در Rust داده داخل خود mutex است (`Mutex<T>`)، پس بدون قفل‌کردن نمی‌توانید به آن برسید. `lock()` یک guard برمی‌گرداند و قفل وقتی guard از بین برود آزاد می‌شود. اگر thread در حال نگه‌داشتن قفل panic کند، mutex «مسموم» (poisoned) می‌شود و `lock()` یک `Err` برمی‌گرداند.
