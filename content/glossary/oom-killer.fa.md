+++
title = 'OOM killer'
fa_title = 'OOM killer'
summary = 'سازوکار کرنل که وقتی حافظه تمام شود، چه در کل سیستم و چه در cgroupی که به memory.max رسیده، یک پروسه را می‌کشد.'
category = 'Linux'
related = ["cgroup", "container"]
posts = ["linux-cgroups-namespaces", "linux-memory-page-cache-oom"]
+++

طبق مستندات cgroup v2 وقتی مصرف به `memory.max` برسد و کم نشود، OOM killer در همان cgroup فعال می‌شود و `memory.events` آن را در `oom_kill` می‌شمارد.
