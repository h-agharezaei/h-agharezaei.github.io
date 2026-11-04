+++
title = "LTO"
fa_title = "LTO (بهینه‌سازی در زمان link)"
summary = "بهینه‌سازی در زمان link: کامپایلر در پایان build همه‌ی crateها را با هم بهینه می‌کند و باینری کوچک‌تر و اغلب سریع‌تر می‌دهد، به قیمت زمان build بیشتر."
category = "Rust"
related = ["crate"]
posts = ["rust-docker-ci-release"]
+++

به‌طور معمول هر crate جداگانه بهینه می‌شود و بعد link می‌شود. با LTO کامپایلر کل برنامه را می‌بیند، پس می‌تواند کد استفاده‌نشده را حذف کند و تابع‌ها را بین مرز crateها inline کند. در Cargo آن را با `lto = "thin"` یا `lto = "fat"` در `[profile.release]` روشن می‌کنید؛ fat کامل‌ترین و کندترین حالت build است.
