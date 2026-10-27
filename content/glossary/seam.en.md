+++
title = "Seam"
summary = "A place where you can change behavior without editing the code around it."
category = "Engineering"
related = ["dependency-injection", "legacy-code", "characterization-test"]
posts = ["eng-legacy-code"]
+++

In Go a seam is often a function variable (`var now = time.Now`), a small interface or a parameter. Tests replace what is behind the seam, such as the clock or the database.
