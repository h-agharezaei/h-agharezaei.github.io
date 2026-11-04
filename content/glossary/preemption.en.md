+++
title = "Preemption"
summary = "Interrupting a running goroutine or thread so that others get a turn, without waiting for it to give up the CPU."
category = "Go"
related = ["goroutine", "garbage-collector"]
posts = ["go-scheduler-gc-internals"]
+++

Cooperative scheduling can only switch at points the code chooses, such as function calls, so a loop with none can hog its processor. Preemption lets the scheduler stop it anyway. According to the Go release notes, Go has interrupted such loops asynchronously since Go 1.14.
