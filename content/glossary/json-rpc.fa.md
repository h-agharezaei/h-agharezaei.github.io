+++
title = "JSON-RPC"
summary = "پروتکل کوچک فراخوانی از راه دور: درخواست JSON با method، params و id، و جواب JSON با result یا error."
category = "Networking"
fa_title = "JSON-RPC"
related = ["full-node"]
posts = ["bc-toy-node-go", "bc-go-ethereum-client", "bc-rust-alloy-client"]
+++

نسخه‌ی 2.0 به لایه‌ی انتقال وابسته نیست؛ نودهای بلاکچین معمولاً آن را روی HTTP یا WebSocket ارائه می‌کنند. مثال: `{"jsonrpc":"2.0","id":1,"method":"getblockcount","params":[]}`.
