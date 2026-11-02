+++
title = "Storage packing"
summary = "تعریف متغیرهای state کوچک کنار هم تا Solidity آن‌ها را در یک slot سی‌ودوبایتی نگه دارد."
category = "Blockchain"
fa_title = "فشرده‌سازی storage (storage packing)"
related = ["storage-layout", "gas", "evm"]
posts = ["bc-gas-optimization-proxies"]
+++

slot کمتر یعنی خواندن و نوشتن گران کمتر وقتی مقدارها با هم استفاده می‌شوند، مثل دو موجودی `uint112` و یک timestamp از نوع `uint32`. نوع کوچک‌تر cast چک‌شده می‌خواهد، چون cast بی‌صدا می‌بُرد.
