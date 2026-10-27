+++
title = "inline script metadata"
summary = "PEP 723: بلوک کامنت بالای یک اسکریپت تک‌فایلی که وابستگی‌ها و نسخه‌ی Python را فهرست می‌کند."
category = "Python"
fa_title = "inline script metadata"
related = ["virtual-environment", "pyproject-toml"]
posts = ["py-cli-scripts"]
+++

بلوک کامنت `# /// script` شامل TOML است، مثلاً `dependencies = [...]`. ابزارهایی مثل `uv run script.py` آن را می‌خوانند، یک محیط کش‌شده می‌سازند و اسکریپت را اجرا می‌کنند؛ پس یک فایل می‌تواند نیازمندی‌هایش را با خودش حمل کند.
