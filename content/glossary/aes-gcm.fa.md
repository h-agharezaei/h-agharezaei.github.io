+++
title = "AES-GCM"
summary = "حالت رمزنگاری احراز‌شده: داده را پنهان می‌کند و هر تغییرش را تشخیص می‌دهد."
category = "Security"
fa_title = "AES-GCM"
related = ["nonce"]
posts = ["sec-secrets-management", "sec-crypto-mistakes"]
+++

Go آن را با `cipher.NewGCM` می‌دهد. برای هر پیام نانس یکتا می‌خواهد و می‌تواند داده‌ی اضافه (AAD) مثل شناسه‌ی رکورد را به متن رمزشده ببندد.
