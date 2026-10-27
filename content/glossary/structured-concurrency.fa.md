+++
title = "Structured concurrency"
fa_title = "structured concurrency"
summary = "سبکی که در آن taskهای هم‌زمان درون یک scope زندگی می‌کنند؛ scope منتظر همه می‌ماند و اگر یکی شکست بخورد بقیه را لغو می‌کند."
category = "Python"
related = ["coroutine", "exception-group"]
posts = ["py-asyncio"]
+++

سبکی که در آن taskهای هم‌زمان درون یک scope زندگی می‌کنند؛ scope منتظر همه می‌ماند و اگر یکی شکست بخورد بقیه را لغو می‌کند. در Python، `asyncio.TaskGroup` همین را می‌دهد: هیچ taskی از بلوک `async with` بیرون نمی‌ماند و خطاها در یک ExceptionGroup جمع می‌شوند.
