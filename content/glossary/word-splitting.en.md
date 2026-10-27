+++
title = "Word splitting"
summary = "The shell step that splits an unquoted expansion into separate words."
category = "Linux"
related = ["xargs", "exit-status"]
posts = ["linux-scripting-cron-safely"]
+++

After expanding a variable, the shell splits the result on spaces, tabs and newlines (IFS) and then applies globbing. Quoting an expansion as "$var" prevents both.
