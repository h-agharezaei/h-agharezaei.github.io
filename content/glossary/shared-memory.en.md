+++
title = "shared memory"
summary = "A block of memory that several processes map at once, so they can read and write the same bytes without copying."
category = 'Python'
related = ["process", "pickle"]
posts = ["py-multiprocessing"]
+++

Normally each [process](/glossary/process/) has its own memory. A shared memory block is mapped by several, so no copying or pickling is needed, but you must synchronize access yourself and release it (in Python: `close()` in each process, `unlink()` once).
