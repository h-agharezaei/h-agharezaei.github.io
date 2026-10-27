+++
title = "Coroutine"
summary = "A function defined with async def; calling it returns a coroutine object that does nothing until it is awaited or wrapped in a task."
category = "Python"
related = ["event-loop", "async-await"]
posts = ["py-asyncio"]
+++

A function defined with async def; calling it returns a coroutine object that does nothing until it is awaited or wrapped in a task. A coroutine can pause at each await and let the event loop run something else, then resume where it stopped. Calling `f()` only creates the object; nothing runs yet.
