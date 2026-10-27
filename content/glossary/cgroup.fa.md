+++
title = 'cgroup'
fa_title = 'cgroup'
summary = 'گروه‌بندی پروسه‌ها در کرنل Linux برای محدود کردن و شمارش مصرف CPU، حافظه و تعداد پروسه.'
category = 'Linux'
related = ["namespace", "container", "oom-killer"]
posts = ["linux-cgroups-namespaces", "linux-memory-page-cache-oom"]
+++

هر cgroup یک پوشه در یک درخت است که در نسخه‌ی ۲ معمولاً زیر `/sys/fs/cgroup` قرار دارد. با نوشتن PID در `cgroup.procs` پروسه را داخلش می‌گذارید و فایل‌هایی مثل `memory.max` و `pids.max` سقف تعیین می‌کنند؛ این‌ها طبق مستندات کرنل است.
