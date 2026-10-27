+++
title = 'Build tag'
summary = 'A `//go:build` line at the top of a Go file that selects the OS or conditions the file compiles under.'
category = 'Linux'
related = []
posts = ["linux-proc-observability", "linux-cgroups-namespaces"]
+++

The line `//go:build linux` makes a Go file compile only on Linux; `//go:build !linux` marks its counterpart. A file name like `x_linux.go` has the same effect.
