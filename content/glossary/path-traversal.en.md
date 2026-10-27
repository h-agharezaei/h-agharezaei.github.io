+++
title = "Path traversal"
summary = "A bug where `../` in user input makes a file handler read outside its intended directory."
category = "Security"
related = ["command-injection"]
posts = ["sec-injection-xss"]
+++

Joining user input to a base directory is not enough, because the joined path is cleaned and can climb out. Check the result against the base, or better use `os.OpenRoot`, which also stops symlinks that point outside.
