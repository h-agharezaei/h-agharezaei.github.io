+++
title = "NXDOMAIN"
summary = "کد پاسخ DNS به معنی «این نام وجود ندارد»."
category = "Networking"
fa_title = "اِن‌اِکس‌دامین"
related = ["dns", "ttl"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute"]
+++

NXDOMAIN همان RCODE شماره‌ی ۳ است. با NOERROR و پاسخ خالی فرق دارد؛ آن یعنی نام هست ولی رکوردی از نوع پرسیده‌شده ندارد. resolverها پاسخ منفی را هم cache می‌کنند.
