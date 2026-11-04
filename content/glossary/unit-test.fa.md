+++
title = "Unit test (Rust)"
fa_title = "unit test در Rust"
summary = "یک تست کوچک که در همان فایل کدی که بررسی می‌کند قرار دارد، داخل ماژولی با #[cfg(test)]."
category = "Rust"
related = ["doc-test", "rust-integration-test", "cargo"]
posts = ["rust-testing-docs"]
+++

در Rust تست‌های واحد کنار کد و در یک ماژول فرزند با علامت `#[cfg(test)]` می‌نشینند که فقط برای `cargo test` کامپایل می‌شود. چون ماژول فرزند است، با `use super::*` به چیزهای خصوصی هم دسترسی دارد. تست تابعی است با علامت `#[test]` که اگر panic کند شکست می‌خورد.
