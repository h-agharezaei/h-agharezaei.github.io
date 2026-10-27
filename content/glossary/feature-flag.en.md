+++
title = "Feature flag"
summary = "a runtime switch that turns code paths on or off without a deploy."
category = "Engineering"
related = ["kill-switch","canary-release","trunk-based-development"]
posts = ["eng-feature-flags-trunk-based"]
+++

A feature flag (or toggle) is a condition in the code whose value comes from configuration, not from the build. It lets you merge unfinished work, release gradually, and switch a feature off quickly. The cost is more code paths to test and flags to remove later.
