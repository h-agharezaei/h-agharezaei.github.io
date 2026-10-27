+++
title = "Structured concurrency"
summary = "A style where concurrent tasks live inside a scope that waits for all of them and cancels the rest if one fails."
category = "Python"
related = ["coroutine", "exception-group"]
posts = ["py-asyncio"]
+++

A style where concurrent tasks live inside a scope that waits for all of them and cancels the rest if one fails. In Python, `asyncio.TaskGroup` gives this: no task outlives the `async with` block, and errors are collected into an ExceptionGroup.
