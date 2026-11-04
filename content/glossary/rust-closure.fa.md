+++
title = "Closure (Rust)"
fa_title = "closure در Rust"
summary = "یک تابع بی‌نام به شکل |args| body که می‌تواند از متغیرهای جایی که ساخته شده استفاده کند."
category = "Rust"
related = ["trait", "borrowing", "ownership"]
posts = ["rust-closures-iterators"]
+++

closure یک تابع کوچک بی‌نام است که می‌تواند متغیرهای محیط اطرافش را بخواند، تغییر بدهد یا مالکیتشان را بگیرد. Rust خودش تصمیم می‌گیرد هر متغیر چگونه گرفته شود (با reference، با reference تغییرپذیر یا با move) و بر همین اساس یک یا چند trait از `Fn`، `FnMut` و `FnOnce` به closure می‌دهد. مثال: `let add = |x| x + n;`.
