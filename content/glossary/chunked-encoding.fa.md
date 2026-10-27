+++
title = "Chunked encoding"
summary = "روشی در HTTP/1.1 برای فرستادن body تکه‌تکه بدون دانستن طول کل."
category = "Networking"
fa_title = "chunked"
related = ["http", "message-framing"]
posts = ["net-http1-by-hand"]
+++

با `Transfer-Encoding: chunked` هر تکه یک اندازه‌ی hex، CRLF، داده و CRLF است. تکه‌ای با اندازه‌ی ۰ پایان body را نشان می‌دهد.
