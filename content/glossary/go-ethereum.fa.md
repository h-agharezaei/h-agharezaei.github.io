+++
title = "go-ethereum (geth)"
fa_title = "go-ethereum (geth)"
summary = "پیاده‌سازی Go کلاینت اجرای اتریوم؛ پکیج‌هایش (ethclient، types، crypto، abi) به‌عنوان کتاب‌خانه‌ی Go هم استفاده می‌شوند."
category = "Blockchain"
related = ["json-rpc", "evm", "abigen"]
posts = ["bc-go-ethereum-client", "bc-event-indexer-go"]
+++

`ethclient` روی API از نوع [JSON-RPC](/fa/glossary/json-rpc/) نود متدهای Go با نوع مشخص می‌گذارد، مثل `ChainID`، `BalanceAt` و `SendTransaction`. همین ماژول [abigen](/fa/glossary/abigen/) را هم دارد که از ABI قرارداد کد Go می‌سازد.
