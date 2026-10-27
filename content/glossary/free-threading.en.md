+++
title = "Free-threaded Python"
summary = "A CPython build, available since 3.13 as an option, that runs without the GIL."
category = "Python"
related = ["gil", "thread"]
posts = ["py-gil-threading"]
+++

In a free-threaded build (`python3.14t`) Python threads can run on several cores at once. Code that relied on the GIL to hide races, such as `counter += 1`, can then lose updates. See [GIL](/glossary/gil/).
