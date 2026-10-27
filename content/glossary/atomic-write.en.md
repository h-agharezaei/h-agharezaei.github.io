+++
title = "Atomic write"
summary = "Writing a file so readers see either the old or the new content, never a half-written one."
category = "Linux"
related = ["file-permissions", "race-condition"]
posts = ["linux-scripting-cron-safely"]
+++

The usual recipe is to write to a temporary file in the same directory and then rename it over the target. On POSIX filesystems a rename within one filesystem replaces the name in one step.
