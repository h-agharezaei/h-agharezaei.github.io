+++
title = "Schnorr protocol"
summary = "اثبات سه‌مرحله‌ای دانستن لگاریتم گسسته: تعهد R = r·G، گرفتن challenge c و جواب s = r + c·x؛ پایه‌ی امضای Schnorr هم هست."
category = "Blockchain"
fa_title = "پروتکل Schnorr"
related = ["zero-knowledge-proof", "fiat-shamir", "discrete-logarithm", "nonce"]
posts = ["bc-zero-knowledge-rust"]
+++

verifier چک می‌کند s·G == R + c·X. با [Fiat-Shamir](/fa/glossary/fiat-shamir/) به امضا تبدیل می‌شود؛ امضاهای BIP-340 بیت‌کوین Schnorr روی secp256k1 هستند. تکرار r برای دو challenge مقدار x را لو می‌دهد.
