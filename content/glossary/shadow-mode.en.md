+++
title = "Shadow mode"
summary = "Running the new implementation next to the old one on real inputs, serving only the old answer and counting differences."
category = "Engineering"
related = ["strangler-fig", "characterization-test", "feature-flag"]
posts = ["eng-legacy-code"]
+++

It shows how the new code would behave before any user depends on it. The mismatches are a to-do list: each one is either a bug in the new code or a quirk of the old one you must decide about.
