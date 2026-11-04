+++
title = "Integration test (Rust)"
fa_title = "integration test در Rust"
summary = "تستی در پوشه‌ی tests/ که کتابخانه‌ی شما را فقط از راه API عمومی‌اش به کار می‌برد، مثل یک کاربر بیرونی."
category = "Rust"
related = ["unit-test", "crate", "doc-test"]
posts = ["rust-testing-docs"]
+++

هر فایل در `tests/` به‌صورت یک crate جدا کامپایل می‌شود که به کتابخانه‌ی شما وابسته است، پس فقط می‌تواند چیزهای عمومی را صدا بزند. فقط برای crate از نوع کتابخانه (با `lib.rs`) کار می‌کند و هر فایل یک برنامه‌ی تست جدا می‌شود.
