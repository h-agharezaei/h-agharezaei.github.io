+++
title = "Subscriber (tracing)"
fa_title = "subscriber در tracing"
summary = "بخشی از اکوسیستم tracing که رویدادها و spanها را دریافت می‌کند و تصمیم می‌گیرد با آن‌ها چه کند: فیلتر، چاپ، قالب JSON یا ارسال به بیرون."
category = "Rust"
related = ["tracing-span"]
posts = ["rust-tracing-observability"]
+++

کدی که با `tracing` مجهز شده فقط رویداد و span اعلام می‌کند. تا برنامه یک subscriber نصب نکند، که معمولاً یک بار ابتدای `main` انجام می‌شود، چیزی چاپ نمی‌شود. crate به نام `tracing-subscriber` یک نمونه‌ی آماده به نام `fmt` دارد که خط‌ها را در کنسول چاپ می‌کند و می‌شود آن را با یک فیلتر (`EnvFilter`) و قالب JSON ترکیب کرد. بدون subscriber رویدادها دور ریخته می‌شوند.
