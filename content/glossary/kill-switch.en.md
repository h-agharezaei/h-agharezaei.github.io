+++
title = "Kill switch"
summary = "a flag whose only job is to turn a feature off at once."
category = "Engineering"
related = ["feature-flag"]
posts = ["eng-feature-flags-trunk-based"]
+++

A kill switch is a flag that overrides every other rule and turns a feature off for everyone. Because it needs no deploy, it is a fast first response when a new path misbehaves in production.
