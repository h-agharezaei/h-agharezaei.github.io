+++
title = "perf"
summary = "Linux performance tool that counts hardware events and samples where CPU time goes."
category = "Linux"
related = ["cpu-profile", "flame-graph", "linux-capabilities"]
posts = ["linux-strace-perf"]
+++

**perf** has `perf stat` to count events (cycles, instructions, context switches) and `perf record` plus `perf report` to sample stacks over time. Sampling costs less than tracing every call, and the samples can be drawn as a [flame-graph](/glossary/flame-graph/).
