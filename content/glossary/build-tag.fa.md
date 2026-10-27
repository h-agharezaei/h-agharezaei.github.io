+++
title = 'Build tag'
fa_title = 'build tag'
summary = 'خط `//go:build` بالای فایل Go که تعیین می‌کند فایل برای کدام سیستم‌عامل یا شرایط کامپایل شود.'
category = 'Linux'
related = []
posts = ["linux-proc-observability", "linux-cgroups-namespaces"]
+++

خط `//go:build linux` بالای یک فایل Go باعث می‌شود آن فایل فقط روی Linux کامپایل شود. با `//go:build !linux` فایل مکمل را می‌نویسید. اسم فایل مثل `x_linux.go` هم همین اثر را دارد.
