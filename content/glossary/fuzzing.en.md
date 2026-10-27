+++
title = "Fuzzing"
summary = "Feeding a program automatically mutated inputs, guided by coverage, to find crashes and bugs."
category = "Engineering"
related = ["property-based-testing", "shrinking"]
posts = ["eng-property-based-testing", "sec-fuzzing"]
+++

A fuzzer starts from seed inputs, mutates them and keeps those that reach new code. Go has it built in: `go test -fuzz FuzzName -fuzztime 5s`. It is related to property-based testing but runs until stopped.
