+++
title = "start method"
summary = "How multiprocessing creates a child process: spawn (fresh interpreter), fork (copy of the parent) or forkserver."
category = 'Python'
related = ["process", "pickle"]
posts = ["py-multiprocessing"]
+++

The start method decides how a child [process](/glossary/process/) begins. With `spawn` a fresh interpreter imports your main module again (hence the `if __name__ == '__main__':` guard); `fork` copies the parent. `multiprocessing.get_start_method()` shows the current one.
