+++
title = "GIL"
summary = "قفلی در CPython استاندارد که اجازه می‌دهد در هر لحظه فقط یک thread بایت‌کد Python اجرا کند."
category = "Python"
fa_title = "گیل (GIL)"
related = ["free-threading", "thread"]
posts = ["py-gil-threading", "py-ffi-pyo3-ctypes"]
+++

Global Interpreter Lock از وضعیت داخلی interpreter محافظت می‌کند. thread‌ها هنگام انتظار I/O هنوز مفیدند چون قفل در زمان بلاک‌شدن آزاد می‌شود، ولی کد CPU-bound در thread‌ها موازی اجرا نمی‌شود. [free-threading](/fa/glossary/free-threading/) را ببینید.
