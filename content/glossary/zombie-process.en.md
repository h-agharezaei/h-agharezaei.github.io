+++
title = 'Zombie process'
summary = 'A child that has exited but whose parent has not yet called `wait`, so its table entry remains.'
category = 'Linux'
related = ["process", "signal"]
posts = ["linux-processes-signals"]
+++

A child that has exited but whose parent has not yet called `wait`, so its table entry remains. It shows state `Z` in `ps`. It cannot be killed; it disappears when the parent reaps it or exits.
