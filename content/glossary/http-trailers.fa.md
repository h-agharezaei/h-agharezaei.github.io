+++
title = "HTTP trailers"
summary = "فیلدهای هدری که بعد از body فرستاده می‌شوند، وقتی نتیجه‌ی نهایی معلوم شده است."
category = "Networking"
fa_title = "تریلر HTTP (trailers)"
related = ["grpc", "multiplexing"]
posts = ["net-grpc-over-http2"]
+++

تریلرها بلوک دوم هدرها هستند که بعد از body می‌آید. HTTP/2 اجازه‌ی آن را روی هر پاسخ می‌دهد. [gRPC](/fa/glossary/grpc/) از آن برای `grpc-status` و `grpc-message` استفاده می‌کند، چون نتیجه‌ی یک فراخوانی بعد از فرستادن آخرین پیام معلوم می‌شود.
