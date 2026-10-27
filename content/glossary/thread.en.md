+++
title = "Thread"
summary = "An independent flow of execution inside a process that shares its memory with other threads."
category = "Python"
related = ["race-condition", "mutex", "gil"]
posts = ["py-gil-threading"]
+++

Threads of one process see the same variables, which makes sharing cheap and makes unsynchronized writes dangerous. The OS schedules them; see [race condition](/glossary/race-condition/).
