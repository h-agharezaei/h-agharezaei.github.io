+++
title = "checksum database"
summary = "یک لاگ عمومی و فقط‌افزودنی از hash ماژول‌ها (Go از sum.golang.org استفاده می‌کند) که تغییر ماژول بین کاربران را تشخیص می‌دهد."
category = "Security"
fa_title = "پایگاه checksum"
related = ["checksum", "lockfile", "software-supply-chain"]
posts = ["sec-supply-chain-vulns"]
+++

اولین بار که ماژولی اضافه می‌کنید، Go hash آن را با این پایگاه مقایسه و در go.sum ثبت می‌کند. دانلودهای بعدی باید با go.sum بخوانند.
