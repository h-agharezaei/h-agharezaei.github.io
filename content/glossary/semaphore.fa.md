+++
title = "Semaphore"
fa_title = "سمافور"
summary = "شیء مبتنی بر شمارنده که حداکثر N نفر را هم‌زمان راه می‌دهد و بقیه منتظر می‌مانند."
category = "Python"
related = ["coroutine", "queue"]
posts = ["py-asyncio", "ds-circuit-breaker-bulkhead"]
+++

شیء مبتنی بر شمارنده که حداکثر N نفر را هم‌زمان راه می‌دهد و بقیه منتظر می‌مانند. برای سقف گذاشتن روی هم‌زمانی استفاده می‌شود، مثلاً حداکثر ۳ درخواست هم‌زمان. در asyncio همان `asyncio.Semaphore(3)` با `async with` است.
