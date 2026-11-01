+++
title = "alloy"
fa_title = "alloy"
summary = "کتاب‌خانه‌ی Rust برای اتریوم: provider روی JSON-RPC، امضاکننده‌ی محلی، ساختن تراکنش و ماکروی sol! برای نوع‌های قرارداد."
category = "Blockchain"
related = ["json-rpc", "sol-macro", "go-ethereum", "contract-abi"]
posts = ["bc-rust-alloy-client"]
+++

alloy در Rust همان کاری را می‌کند که پکیج‌های `ethclient` و `bind` از [go-ethereum](/fa/glossary/go-ethereum/) در Go می‌کنند. یک `Provider` روی API از نوع [JSON-RPC](/fa/glossary/json-rpc/) نود سوار می‌شود؛ وقتی کیف‌پول به آن وصل باشد، fillerها قبل از امضا nonce، سقف gas، کارمزد و chain ID تراکنش را پر می‌کنند.
