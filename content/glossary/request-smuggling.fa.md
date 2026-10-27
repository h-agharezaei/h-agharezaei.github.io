+++
title = "Request smuggling"
summary = "حمله‌ای که از اختلاف دو parser HTTP درباره‌ی پایان درخواست سوءاستفاده می‌کند."
category = "Networking"
fa_title = "request smuggling"
related = ["http", "chunked-encoding"]
posts = ["net-http1-by-hand"]
+++

وقتی ممکن می‌شود که مثلاً یک proxy و backend درباره‌ی اینکه `Content-Length` طول body را تعیین می‌کند یا `Transfer-Encoding` اختلاف داشته باشند. اینجا فقط مفهوم است؛ سری امنیت به دفاع می‌پردازد.
