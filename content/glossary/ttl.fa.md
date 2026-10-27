+++
title = "TTL"
summary = "تعداد ثانیه‌هایی که رکورد cache‌شده بدون پرسش دوباره قابل استفاده است."
category = "Networking"
fa_title = "تی‌تی‌اِل"
related = ["dns", "recursive-resolver"]
posts = ["net-dns-in-practice", "net-troubleshooting-curl-traceroute", "ds-service-discovery-load-balancing"]
+++

هر رکورد DNS یک TTL دارد. resolverِ cache‌کننده آن را کم می‌کند، پس پرسش‌های پشت‌سرهم عدد کوچک‌تری نشان می‌دهند تا منقضی شود و دوباره از authoritative server بپرسد.
