+++
title = "Mutation testing"
summary = "Judging a test suite by whether it fails when the code is deliberately broken."
category = "Engineering"
related = ["characterization-test", "tdd"]
posts = ["eng-refactoring-safely"]
+++

A tool makes many small changes (mutants) such as turning >= into >, and runs the tests on each. A mutant that no test catches shows a gap that line coverage cannot show.
