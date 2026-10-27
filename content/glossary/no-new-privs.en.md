+++
title = "no_new_privs"
summary = "A per-thread flag, set with prctl, that stops execve from granting more privilege through setuid bits or file capabilities. Once set it cannot be unset."
category = 'Linux'
related = ["linux-capabilities", "setuid"]
posts = ["linux-users-sudo-capabilities"]
+++

A per-thread flag, set with prctl, that stops execve from granting more privilege through setuid bits or file capabilities. Once set it cannot be unset.
