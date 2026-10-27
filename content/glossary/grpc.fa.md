+++
title = "gRPC"
summary = "چارچوب RPC باینری که روی HTTP/2 و Protocol Buffers ساخته شده است."
category = "Go"
fa_title = "جی‌آر‌پی‌سی"
related = ["ffi"]
posts = ["go-grpc-service", "go-rust-grpc-interop", "net-grpc-over-http2"]
+++

سرویس‌ها و پیام‌ها در فایل‌های `.proto` تعریف می‌شوند و از روی آن‌ها کد client و server برای زبان‌های مختلف تولید می‌شود، برای همین برای ارتباط Go↔Rust مناسب است. هم call ساده و هم streaming یک‌طرفه و دوطرفه را پشتیبانی می‌کند.
