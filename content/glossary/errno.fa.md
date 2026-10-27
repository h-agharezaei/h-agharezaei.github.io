+++
title = "errno"
fa_title = "errno"
summary = "کد خطایی که فراخوان سیستمی ناموفق گزارش می‌کند، مثل ENOENT یا EACCES."
category = "Linux"
related = ["syscall", "strace"]
posts = ["linux-strace-perf"]
+++

**errno** شماره‌ی خطایی است که فراخوان سیستمی ناموفق به جا می‌گذارد؛ strace نماد آن را چاپ می‌کند، مثلاً `-1 ENOENT (No such file or directory)`. خواندن همین نماد معمولاً می‌گوید بعد چه را بررسی کنی.
