+++
title = "Shrinking"
summary = "Reducing a failing random input to the smallest one that still fails."
category = "Engineering"
related = ["property-based-testing", "fuzzing"]
posts = ["eng-property-based-testing"]
+++

When a property fails on a large random input, the library tries smaller variants and keeps the smallest that still fails. You debug `[0 1 0]` instead of a 37-element slice.
