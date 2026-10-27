+++
title = "HTTP"
summary = "پروتکل متنی درخواست و پاسخ که معمولاً روی TCP حمل می‌شود."
category = "Networking"
fa_title = "اچ‌تی‌تی‌پی"
related = ["tcp", "message-framing"]
posts = ["net-http1-by-hand", "net-websocket", "net-grpc-over-http2", "net-troubleshooting-curl-traceroute"]
+++

HTTP/1.1 یک پروتکل متنی است: خط درخواست، چند خط header، یک خط خالی و در صورت لزوم body که همه با CRLF جدا می‌شوند. سرور با خط وضعیت، header، خط خالی و body جواب می‌دهد.
