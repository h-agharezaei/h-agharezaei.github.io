+++
title = "Go workspace (go.work)"
summary = "A go.work file that makes several local Go modules resolve to each other without published versions."
category = "Engineering"
related = ["monorepo"]
posts = ["eng-monorepo-vs-polyrepo"]
+++

A `go.work` file lists directories with `use`. While it is active, the go command builds the listed modules together and prefers the local copies over versions from a registry. It is meant for local development across modules, such as in a [monorepo](/glossary/monorepo/).
