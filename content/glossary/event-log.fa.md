+++
title = "Event log"
fa_title = "رویداد و log"
summary = "داده‌ای که قرارداد در رسید تراکنش منتشر می‌کند: تا ۴ topic قابل جست‌وجو و یک data؛ بیرون زنجیره خواندنی است ولی قراردادها نمی‌توانند بخوانندش."
category = "Blockchain"
related = ["solidity", "erc-20", "keccak-256"]
posts = ["bc-solidity-first-contract", "bc-erc20-erc721", "bc-event-indexer-go"]
+++

topic اول معمولاً `keccak256` امضای رویداد است و پارامترهای `indexed` بقیه‌ی topicها می‌شوند. کیف پول‌ها و indexerها انتقال‌ها را با فیلتر کردن logها پیدا می‌کنند و برای همین [ERC-20](/fa/glossary/erc-20/) رویداد `Transfer` را الزامی کرده.
