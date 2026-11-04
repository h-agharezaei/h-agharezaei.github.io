+++
title = "Newtype"
fa_title = "newtype"
summary = "struct تک‌فیلدی که یک type دیگر را می‌پوشاند تا هویت جدا داشته باشد، مثل UserId(u64) در برابر OrderId(u64)."
category = "Rust"
related = ["type-state"]
posts = ["rust-typestate-patterns"]
+++

`struct UserId(u64);` و `struct OrderId(u64);` همان داده‌ی یک `u64` ساده را نگه می‌دارند، ولی کامپایلر آن‌ها را دو type جدا می‌بیند، پس دادن یکی به‌جای دیگری خطا می‌شود. اگر فیلد خصوصی باشد و تنها constructor ورودی را اعتبارسنجی کند، هر مقدار از آن type حتماً معتبر است. newtype در زمان اجرا هزینه‌ای ندارد: اندازه‌ی `UserId` با `u64` برابر است.
