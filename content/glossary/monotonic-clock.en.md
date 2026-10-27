+++
title = "Monotonic clock"
summary = "A clock that only moves forward and is meant for measuring durations, not for telling the date."
category = "Distributed"
related = ["clock-skew"]
posts = ["ds-why-distributed-is-hard"]
+++

Wall-clock time can jump when it is corrected, so subtracting two wall times can give a negative duration. In Go, `time.Now()` carries a monotonic reading too, and `Sub` uses it when both values have one.
