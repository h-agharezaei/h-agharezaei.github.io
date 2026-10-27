+++
title = "Deadline"
summary = "زمانی مطلق که بعد از آن خواندن یا نوشتن روی شبکه با خطای timeout شکست می‌خورد."
category = "Networking"
fa_title = "ددلاین"
related = ["socket", "context"]
posts = ["net-sockets-tcp-from-scratch", "net-udp-sockets", "db-connection-pooling", "net-websocket", "net-grpc-over-http2", "ds-why-distributed-is-hard"]
+++

در Go، `SetReadDeadline` یک زمان (نه مدت) روی اتصال می‌گذارد؛ Read که هنوز بلاک است بعد از آن با خطای `i/o timeout` برمی‌گردد. برای idle timeout باید پیش از هر خواندن دوباره آن را تنظیم کنید. برای لغو به‌طور کلی به [context](/fa/glossary/context/) نگاه کنید.
