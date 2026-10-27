+++
title = "GOAWAY"
summary = "فریمی در HTTP/2 که به طرف مقابل می‌گوید روی این اتصال stream تازه باز نکند."
category = "Networking"
fa_title = "GOAWAY در HTTP/2"
related = ["multiplexing", "graceful-shutdown"]
posts = ["net-grpc-over-http2"]
+++

فریم GOAWAY شماره‌ی آخرین streamی را دارد که فرستنده پردازش می‌کند. streamهای تا آن شماره می‌توانند تمام شوند و بقیه باید روی اتصال دیگری دوباره امتحان شوند. سرور HTTP/2 یا gRPC با آن اتصال را پیش از بستن تخلیه می‌کند.
