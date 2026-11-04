+++
title = "wasm-bindgen"
fa_title = "wasm-bindgen"
summary = "یک crate و ابزار خط فرمان که کد چسباننده‌ی JavaScript لازم برای رد کردن رشته و شیء بین Rust کامپایل‌شده به wasm و JavaScript را تولید می‌کنند."
category = "Rust"
related = ["webassembly"]
posts = ["rust-wasm"]
+++

wasm خام فقط عدد رد می‌کند. تابع Rust را با `#[wasm_bindgen]` علامت می‌زنید، برای `wasm32-unknown-unknown` می‌سازید و دستور `wasm-bindgen` را روی نتیجه اجرا می‌کنید؛ یک فایل `.wasm`، یک wrapper ‏JavaScript و یک فایل تعریف TypeScript می‌نویسد. wrapper کپی رشته‌ها به حافظه‌ی ماژول و از آن را انجام می‌دهد. طبق مستندات آن، ابزار خط فرمان و crate باید یک نسخه باشند.
