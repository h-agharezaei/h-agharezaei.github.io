+++
title = "AggregateError"
summary = "An error that bundles several errors, e.g. what Promise.any rejects with."
category = "Node.js"
related = ["promise"]
posts = ["node-errors-unhandled-rejections"]
+++

It has an `errors` array. `Promise.any` rejects with one when every input promise rejected. See [promise](/glossary/promise/).
