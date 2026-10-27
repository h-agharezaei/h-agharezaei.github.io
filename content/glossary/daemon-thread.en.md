+++
title = "Daemon thread"
summary = "A thread that does not keep the program alive: when only daemon threads remain, the process exits."
category = "Python"
related = ["thread"]
posts = ["py-gil-threading"]
+++

In Python, `Thread(daemon=True)` is stopped abruptly at interpreter exit, so its `finally` blocks and cleanup may never run. Use an `Event` to stop worker threads politely instead.
