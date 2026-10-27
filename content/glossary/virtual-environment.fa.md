+++
title = "virtual environment"
summary = "پوشه‌ای جدا با لینک interpreter و site-packages مخصوص خودش تا هر پروژه وابستگی‌های خودش را داشته باشد."
category = "Python"
fa_title = "محیط مجازی"
related = ["site-packages", "pip", "uv"]
posts = ["py-environment-uv-venv"]
+++

با `python3 -m venv .venv` یا `uv venv` ساخته می‌شود. داخل آن `sys.prefix` با `sys.base_prefix` فرق دارد. [site-packages](/fa/glossary/site-packages/) را هم ببینید.
