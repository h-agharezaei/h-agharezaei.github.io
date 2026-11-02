+++
title = "Storage layout"
fa_title = "چیدمان storage"
summary = "این‌که هر متغیر state قرارداد در کدام اسلات ۳۲ بایتی storage (و با چه offset) قرار می‌گیرد."
category = "Blockchain"
related = ["solidity", "evm", "keccak-256"]
posts = ["bc-solidity-first-contract"]
+++

Solidity اسلات‌ها را به ترتیب تعریف می‌دهد و مقدارهای کوچک را کنار هم فشرده می‌کند. mapping فقط شماره‌ی اسلات `p` را رزرو می‌کند؛ مقدار کلید `k` در `keccak256(k . p)` است. `forge inspect <Contract> storageLayout` آن را چاپ می‌کند.
