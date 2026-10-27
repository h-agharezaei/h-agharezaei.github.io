+++
title = "Rollback"
summary = "Returning production to the previous known-good release, as opposed to rolling forward with a new fix."
category = "Engineering"
related = ["blue-green-deployment", "expand-contract", "feature-flag"]
posts = ["eng-ci-cd-pipeline-design"]
+++

It is easy for code and hard for data: a destructive migration cannot be undone by redeploying old code.
