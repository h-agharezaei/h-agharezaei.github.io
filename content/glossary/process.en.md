+++
title = 'Process'
summary = 'A running instance of a program, with its own pid, memory and a parent process.'
category = 'Linux'
related = ["signal", "zombie-process"]
posts = ["linux-processes-signals"]
+++

A running instance of a program, with its own pid, memory and a parent process. A process is created by its parent (fork or spawn) and ends with an exit status that the parent can read with `wait`.
