+++
title = "Function selector"
fa_title = "function selector"
summary = "چهار بایت اول keccak256 امضای تابع؛ calldata با آن شروع می‌شود تا قرارداد بداند کدام تابع را اجرا کند."
category = "Blockchain"
related = ["keccak-256", "evm", "solidity"]
posts = ["bc-solidity-first-contract", "bc-go-ethereum-client", "bc-rust-alloy-client", "bc-gas-optimization-proxies"]
+++

برای `transfer(address,uint256)` مقدارش `0xa9059cbb` است. کامپایلر یک dispatcher می‌سازد که ۴ بایت اول calldata را با هر selector مقایسه می‌کند. `cast sig` آن را حساب می‌کند.
