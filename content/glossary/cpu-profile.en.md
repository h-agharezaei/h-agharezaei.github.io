+++
title = "CPU profile"
summary = "A sampled record of which functions the CPU was running, used to find where time goes."
category = "Node.js"
related = ["heap-snapshot", "pprof"]
posts = ["node-profiling-memory-shutdown", "linux-strace-perf"]
+++

Node.js writes one with `node --cpu-prof` as a `.cpuprofile` JSON file. Each sample points to a call stack; counting the samples whose top frame is a function gives its self time.
