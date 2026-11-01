+++
title = "Wei"
fa_title = "wei"
summary = "کوچک‌ترین واحد ether: هر ether برابر 10^18 wei است. نود و قرارداد فقط با wei و به شکل عدد صحیح کار می‌کنند."
category = "Blockchain"
related = ["gas", "eip-1559"]
posts = ["bc-go-ethereum-client", "bc-rust-alloy-client"]
+++

قیمت gas معمولاً به gwei (یعنی 10^9 wei) نمایش داده می‌شود. مقدارها راحت از ۶۴ بیت بیشتر می‌شوند، پس کد Go آن‌ها را در `*big.Int` نگه می‌دارد و فقط برای نمایش به ether تبدیل می‌کند.
