+++
title = "Cyclomatic complexity"
summary = "A count of the independent decision paths through a function."
category = "Engineering"
related = ["refactoring"]
posts = ["eng-refactoring-safely", "eng-technical-debt"]
+++

Tools such as gocyclo count one plus each if, for, non-default case and the operators && and ||. A high number means many paths to test and understand. It is a hint about where to look, not a quality score.
