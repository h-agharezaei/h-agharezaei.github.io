+++
title = "Criterion"
fa_title = "Criterion"
summary = "کتاب‌خانه‌ی benchmark آماری برای Rust: گرم می‌کند، نمونه‌های زیادی جمع می‌کند، بازه‌ی اطمینان می‌دهد و با اجراهای قبلی مقایسه می‌کند."
category = "Rust"
related = ["black-box"]
posts = ["rust-performance-criterion"]
+++

آن را به‌عنوان dev-dependency اضافه می‌کنید، فایلی در `benches/*.rs` با `harness = false` می‌نویسید و `cargo bench` را می‌زنید. خروجی `time: [low estimate high]` یک بازه‌ی اطمینان است و اجرای دوم می‌گوید تغییر نسبت به اجرای قبل از نظر آماری معنادار است یا نه.
