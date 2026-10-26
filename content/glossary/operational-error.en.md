+++
title = "Operational error"
summary = "An expected runtime failure (bad input, missing record, timeout), as opposed to a bug."
category = "Node.js"
related = ["unhandled-rejection"]
posts = ["node-errors-unhandled-rejections"]
+++

Operational errors are handled and mapped to a response. Programmer errors (a `TypeError` from a bug) mean the process state is suspect, so the safe reaction is to log and restart.
