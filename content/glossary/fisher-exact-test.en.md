+++
title = "Fisher exact test"
summary = "an exact significance test for a 2x2 table of counts."
category = "Distributed"
related = ["statistical-power", "canary-release"]
posts = ["ds-deployment-strategies"]
+++

Fisher's exact test computes the exact probability of seeing a split of errors at least this lopsided between two groups, from the hypergeometric distribution. Unlike a z-test it stays valid when counts are tiny.
