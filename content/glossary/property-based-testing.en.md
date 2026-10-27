+++
title = "Property-based testing"
summary = "Testing a rule that must hold for all inputs, with inputs generated automatically."
category = "Engineering"
related = ["tdd", "test-pyramid", "shrinking", "fuzzing"]
posts = ["eng-property-based-testing", "algo-shortest-paths-dijkstra", "py-testing-pytest", "algo-topological-sort"]
+++

Instead of fixed examples you state a property (for example, reversing twice gives the original) and the tool generates many random inputs to look for a counterexample. Go has `testing/quick` and the library `rapid`.
