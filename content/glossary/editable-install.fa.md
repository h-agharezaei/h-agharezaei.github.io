+++
title = "editable install"
summary = "نصب یک پروژه به‌گونه‌ای که محیط به نسخه‌ی کاری شما اشاره کند، نه یک کپی ثابت؛ پس تغییرها فوراً اعمال می‌شوند."
category = "Python"
fa_title = "editable install"
related = ["wheel", "virtual-environment", "uv"]
posts = ["py-packaging-publishing"]
+++

با `uv pip install -e .` (یا `pip install -e .`) انجام می‌شود. ماژول‌های import‌شده به فایل‌های داخل پوشه‌ی `src/` شما اشاره می‌کنند.
