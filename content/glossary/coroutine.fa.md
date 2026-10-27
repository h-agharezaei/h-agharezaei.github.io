+++
title = "Coroutine"
fa_title = "کورتین"
summary = "تابعی که با async def تعریف می‌شود؛ صدا زدنش یک شیء coroutine برمی‌گرداند که تا await یا تبدیل به task نشود کاری نمی‌کند."
category = "Python"
related = ["event-loop", "async-await"]
posts = ["py-asyncio"]
+++

تابعی که با async def تعریف می‌شود؛ صدا زدنش یک شیء coroutine برمی‌گرداند که تا await یا تبدیل به task نشود کاری نمی‌کند. coroutine می‌تواند در هر await متوقف شود و event loop کار دیگری اجرا کند، سپس از همان نقطه ادامه دهد. صدا زدن `f()` فقط شیء را می‌سازد و چیزی اجرا نمی‌شود.
