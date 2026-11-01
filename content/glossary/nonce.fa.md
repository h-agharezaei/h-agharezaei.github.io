+++
title = "Nonce"
summary = "مقداری که برای هر کلید فقط یک بار باید استفاده شود، مثل ورودی هر پیام در AES-GCM."
category = "Security"
fa_title = "نانس"
related = ["aes-gcm"]
posts = ["sec-secrets-management", "sec-crypto-mistakes", "bc-account-model-nonce", "bc-keys-ecdsa-addresses", "bc-proof-of-work-mining", "bc-go-ethereum-client", "bc-zero-knowledge-rust", "bc-exchange-deposits-withdrawals"]
+++

در AES-GCM یک نانس ۱۲ بایتی کنار متن رمزشده ذخیره می‌شود. تکرار آن با همان کلید هم محرمانگی و هم اصالت را از بین می‌برد. آن را با `crypto/rand` بسازید.
