+++
title = "EIP-55"
summary = "checksum آدرس اتریوم که در بزرگ و کوچک بودن حروف hex رمز می‌شود."
category = "Blockchain"
fa_title = "EIP-55"
related = ["keccak-256"]
posts = ["bc-keys-ecdsa-addresses"]
+++

آدرس hex با حروف کوچک را با [Keccak-256](/fa/glossary/keccak-256/) hash می‌کنیم؛ هر حرفی که nibble متناظرش در hash ۸ یا بیشتر باشد بزرگ می‌شود. این‌طوری غلط تایپی معمولاً الگوی حروف را خراب می‌کند و پیدا می‌شود.
