+++
title = "Service registry"
summary = "سرویس کوچکی که نگه می‌دارد کدام instanceها زنده‌اند؛ instanceها با یک TTL ثبت می‌شوند و مدام آن را تمدید می‌کنند."
category = "Distributed"
fa_title = "Service registry"
related = ["service-discovery", "ttl", "heartbeat"]
posts = ["ds-service-discovery-load-balancing"]
+++

اگر instance تمدید نکند، ورودی‌اش بعد از [TTL](/fa/glossary/ttl/) منقضی می‌شود. بین crash و انقضا registry کهنه است.
