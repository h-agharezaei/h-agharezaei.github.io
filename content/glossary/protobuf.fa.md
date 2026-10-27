+++
title = "Protocol Buffers"
summary = "قالب باینری فشرده برای پیام‌های ساختاریافته که در فایل .proto تعریف می‌شود."
category = "Networking"
fa_title = "پروتوباف (Protocol Buffers)"
related = ["grpc"]
posts = ["net-grpc-over-http2"]
+++

protobuf هر پیام را به‌صورت جفت‌های «شماره‌ی فیلد و مقدار» کدگذاری می‌کند، نه نام فیلد؛ پس پیام‌ها کوچکند و اضافه شدن فیلد جدید مشکلی ایجاد نمی‌کند. [gRPC](/fa/glossary/grpc/) آن را به‌عنوان قالب پیش‌فرض پیام استفاده می‌کند.
