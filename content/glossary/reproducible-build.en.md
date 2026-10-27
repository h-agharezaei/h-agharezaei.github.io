+++
title = "Reproducible build"
summary = "Building the same source twice gives byte-identical output, so a checksum can prove what was built."
category = "Engineering"
related = ["checksum", "ci"]
posts = ["eng-ci-cd-pipeline-design"]
+++

Paths, timestamps and VCS state can leak into a binary and break this. Compare two builds' hashes to find out.
