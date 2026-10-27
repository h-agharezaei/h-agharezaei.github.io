+++
title = "pickle"
summary = "Python's built-in serialization of objects to bytes, used to send data between processes."
category = 'Python'
related = ["process"]
posts = ["py-multiprocessing", "sec-ssrf-deserialization"]
+++

`pickle` turns a Python object into bytes and back. `multiprocessing` pickles every argument and result it sends to another [process](/glossary/process/), so they must be picklable (a lambda is not) and big objects cost time and bytes.
