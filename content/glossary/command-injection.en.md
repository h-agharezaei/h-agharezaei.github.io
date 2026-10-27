+++
title = "Command injection"
summary = "A bug where user input becomes part of a shell command line and changes what runs."
category = "Security"
related = ["sql-injection", "rce"]
posts = ["sec-injection-xss"]
+++

It appears when a program builds a string and hands it to `sh -c`. The fix is to run the program directly with an argument list and no shell, so the input stays one argument.
