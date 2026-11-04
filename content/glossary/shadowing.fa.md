+++
title = "Shadowing"
fa_title = "Shadowing"
summary = "تعریف متغیر جدید با اسمی که قبلاً داشتیم و پوشاندن متغیر قبلی."
category = "Rust"
related = ["ownership"]
posts = ["rust-types-control-flow"]
+++

در Rust دوباره‌نوشتن `let x = ...` یک متغیر کاملاً جدید می‌سازد که از آن به بعد `x` قبلی را می‌پوشاند. برخلاف تغییر مقدار (`let mut` و انتساب) می‌تواند نوع را عوض کند: `let spaces = spaces.len();` رشته را به عدد تبدیل می‌کند.
