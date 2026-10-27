+++
title = "Message framing"
summary = "قاعده‌هایی که در یک جریان بایتی مثل TCP مشخص می‌کنند هر پیام کجا تمام می‌شود."
category = "Networking"
fa_title = "فریم‌بندی پیام"
related = ["tcp", "stream"]
posts = ["net-sockets-tcp-from-scratch", "net-udp-sockets"]
+++

TCP فقط بایت بدون مرز می‌دهد، پس خود پروتکل باید بگوید پیام کجا تمام می‌شود. دو روش رایج: جداکننده مثل newline، یا length prefix (یک عدد با اندازه‌ی ثابت پیش از payload). به [stream](/fa/glossary/stream/) نگاه کنید.
