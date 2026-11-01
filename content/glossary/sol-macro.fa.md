+++
title = "sol! macro"
fa_title = "ماکروی sol!"
summary = "ماکرویی در alloy که اعلان‌های Solidity را موقع کامپایل می‌خواند و برای فراخوانی‌ها، رویدادها و خطاهای سفارشی نوع Rust می‌سازد."
category = "Blockchain"
related = ["alloy", "contract-abi", "abigen", "function-selector"]
posts = ["bc-rust-alloy-client"]
+++

رابط قرارداد را داخلش می‌نویسید (یا فایل JSON از نوع [ABI](/fa/glossary/contract-abi/) را به آن می‌دهید) و ماکرو برایش structهایی با [selector](/fa/glossary/function-selector/) و encoding درست می‌سازد، به‌اضافه‌ی یک enum برای خطاهای هر قرارداد. برخلاف [abigen](/fa/glossary/abigen/) فایل تولیدشده‌ای در مخزن نمی‌ماند: اگر رابط عوض شود، محل فراخوانی خطای کامپایل می‌دهد.
