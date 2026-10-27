+++
title = "Characterization test"
summary = "A test that records what code does today, bugs included, so you can change it safely."
category = "Engineering"
related = ["refactoring", "regression"]
posts = ["eng-refactoring-safely"]
+++

A characterization test (also called a golden-master or snapshot test) runs the code on many inputs, saves the outputs to a file, and later fails if any output differs. It does not claim the behavior is right, only that it is unchanged.
