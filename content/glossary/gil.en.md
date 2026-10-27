+++
title = "GIL"
summary = "A lock in standard CPython that lets only one thread run Python bytecode at a time."
category = "Python"
related = ["free-threading", "thread"]
posts = ["py-gil-threading"]
+++

The Global Interpreter Lock protects the interpreter's internal state. Threads still help with I/O waits because the lock is released while they block, but CPU-bound Python code in threads does not run in parallel. See [free-threading](/glossary/free-threading/).
