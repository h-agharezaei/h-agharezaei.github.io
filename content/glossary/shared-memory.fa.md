+++
title = "shared memory"
summary = "بلوکی از حافظه که چند پروسه هم‌زمان map می‌کنند و بدون کپی روی همان بایت‌ها می‌خوانند و می‌نویسند."
category = 'Python'
fa_title = 'حافظه‌ی مشترک'
related = ["process", "pickle"]
posts = ["py-multiprocessing"]
+++

معمولاً هر [پروسه](/fa/glossary/process/) حافظه‌ی خودش را دارد. بلوک حافظه‌ی مشترک را چند پروسه map می‌کنند، پس کپی و pickle لازم نیست، اما هماهنگ‌سازی دسترسی با خودتان است و باید آزادش کنید (در Python: `close()` در هر پروسه و یک بار `unlink()`).
