+++
title = "Span (tracing)"
fa_title = "span در tracing"
summary = "بازه‌ای از زمان با فیلدهای نام‌دار که با crate به نام tracing ساخته می‌شود؛ هر رویدادی داخل آن ثبت شود فیلدهای آن را خودکار با خود دارد."
category = "Rust"
related = ["tracing-subscriber", "rust-future"]
posts = ["rust-tracing-observability"]
+++

span مثل برچسبی است که روی یک بازه از کار می‌گذارید، مثلاً `request{request_id="req-7"}`. تا وقتی span فعال است، هر رویداد لاگ داخلش همراه با فیلدهای span چاپ می‌شود. در کد async، span در هر `.await` همراه task می‌ماند، پس حتی وقتی خط‌های چند task قاطی شده باشند می‌شود آن‌ها را از هم تشخیص داد. span‌ها تو در تو هم می‌شوند: مثلاً span به نام `charge` داخل span به نام `handle`.
