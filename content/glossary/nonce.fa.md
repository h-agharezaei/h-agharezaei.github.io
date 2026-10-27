+++
title = "Nonce"
summary = "مقداری که برای هر کلید فقط یک بار باید استفاده شود، مثل ورودی هر پیام در AES-GCM."
category = "Security"
fa_title = "نانس"
related = ["aes-gcm"]
posts = ["sec-secrets-management"]
+++

در AES-GCM یک نانس ۱۲ بایتی کنار متن رمزشده ذخیره می‌شود. تکرار آن با همان کلید هم محرمانگی و هم اصالت را از بین می‌برد. آن را با `crypto/rand` بسازید.
