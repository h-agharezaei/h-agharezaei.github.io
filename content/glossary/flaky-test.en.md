+++
title = "Flaky test"
summary = "A test that sometimes passes and sometimes fails with no change in the code."
category = "Engineering"
related = ["dependency-injection", "test-pyramid"]
posts = ["eng-testing-pyramid-tdd", "eng-property-based-testing", "eng-ci-cd-pipeline-design"]
+++

The usual causes are real time, randomness, shared state, and timing between goroutines. Flaky tests teach people to ignore red builds, so they are worth fixing early, for example by injecting a clock.
