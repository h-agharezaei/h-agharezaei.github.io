+++
title = "Promise"
summary = "A value that stands for a result that is not ready yet: pending, then fulfilled or rejected."
category = "Node.js"
related = ["async-await", "microtask"]
posts = ["node-promises-async-await"]
+++

A promise settles once, to a value or to an error. You attach work with `.then` and `.catch`, or wait for it with [async/await](/glossary/async-await/); the callbacks run as [microtasks](/glossary/microtask/).
