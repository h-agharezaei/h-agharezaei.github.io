+++
title = "TIME_WAIT"
summary = "حالت طرفی که اول اتصال را بسته و مدتی بعد از پایان اتصال در این حالت می‌ماند."
category = "Networking"
fa_title = "TIME_WAIT"
related = ["tcp", "three-way-handshake"]
posts = ["net-tcp-handshake-states", "linux-networking-ip-ss-nftables"]
+++

بعد از بسته‌شدن، طرفی که اول FIN فرستاده مدتی در حالت TIME_WAIT می‌ماند (طبق مستندات حدود دو برابر عمر بیشینه‌ی segment). این کار اجازه می‌دهد بسته‌های دیررسیده از بین بروند و ACK آخرِ گم‌شده دوباره فرستاده شود.
