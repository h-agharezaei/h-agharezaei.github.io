+++
title = 'Container'
fa_title = 'container'
summary = 'یک پروسه‌ی معمولی Linux که با namespace و محدودیت cgroup اختصاصی و معمولاً از یک image اجرا می‌شود.'
category = 'Linux'
related = ["namespace", "cgroup", "overlayfs"]
posts = ["linux-cgroups-namespaces"]
+++

در کرنل چیزی به اسم container وجود ندارد. runtime ترکیبی از namespace، cgroup و یک root filesystem می‌سازد و معمولاً از مشخصات OCI runtime پیروی می‌کند.
