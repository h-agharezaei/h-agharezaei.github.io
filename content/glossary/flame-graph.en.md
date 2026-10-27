+++
title = "Flame graph"
summary = "A picture of sampled stacks where box width shows how often a function was on the stack."
category = "Linux"
related = ["perf", "cpu-profile"]
posts = ["linux-strace-perf"]
+++

A **flame graph** stacks sampled call stacks: the x axis is not time, and a wide box means that function (with its callees) was in many samples. Brendan Gregg's FlameGraph scripts draw them from `perf` output.
