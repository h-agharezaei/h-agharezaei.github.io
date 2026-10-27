+++
title = "Seed corpus"
summary = "The starting inputs given to a fuzzer, ideally real samples."
category = "Security"
related = ["fuzzing", "regression"]
posts = ["sec-fuzzing"]
+++

A seed corpus is a small set of valid inputs (in Go, `f.Add` and files under `testdata/fuzz`). The fuzzer mutates them, so good seeds reach deep code quickly. Failing inputs are saved there and replayed by plain `go test`.
